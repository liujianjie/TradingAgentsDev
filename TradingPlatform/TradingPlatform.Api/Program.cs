using Hangfire;
using Hangfire.InMemory;
using Microsoft.EntityFrameworkCore;
using TradingPlatform.Api.Data;
using TradingPlatform.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddJsonFile("appsettings.local.json", optional: true, reloadOnChange: true);

var apiKeysPath = Path.GetFullPath(Path.Combine(builder.Environment.ContentRootPath, "..", "..", "config", "apikeys.local.json"));
builder.Configuration.AddJsonFile(apiKeysPath, optional: true, reloadOnChange: true);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader());
});

builder.Services.Configure<ApiKeysConfig>(builder.Configuration);
builder.Services.Configure<ServerChanOptions>(builder.Configuration.GetSection("ServerChan"));
builder.Services.Configure<PythonApiOptions>(builder.Configuration.GetSection("PythonApi"));
builder.Services.Configure<ScheduleOptions>(builder.Configuration.GetSection("Schedule"));

var dbPath = Path.GetFullPath(Path.Combine(builder.Environment.ContentRootPath, "..", "..", "data", "tradingplatform.db"));
Directory.CreateDirectory(Path.GetDirectoryName(dbPath)!);
builder.Services.AddDbContext<AppDbContext>(opt =>
    opt.UseSqlite($"Data Source={dbPath}"));

builder.Services.AddHttpClient<IPushService, ServerChanPushService>();
builder.Services.AddHttpClient<IAnalysisService, AnalysisService>();
builder.Services.AddSingleton<IAnalysisOrchestrator, AnalysisOrchestrator>();
builder.Services.AddScoped<IScheduledAnalysisJob, ScheduledAnalysisJob>();

builder.Services.AddHangfire(cfg => cfg
    .SetDataCompatibilityLevel(CompatibilityLevel.Version_180)
    .UseSimpleAssemblyNameTypeSerializer()
    .UseRecommendedSerializerSettings()
    .UseInMemoryStorage());
builder.Services.AddHangfireServer();

var app = builder.Build();

app.Logger.LogInformation("apikeys 配置文件路径: {Path} (存在={Exists})",
    apiKeysPath, File.Exists(apiKeysPath));
app.Logger.LogInformation("SQLite 数据库路径: {Path}", dbPath);

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.EnsureCreated();

    // Lightweight schema migration: add ResultJson column if missing
    var conn = db.Database.GetDbConnection();
    conn.Open();
    using (var pragma = conn.CreateCommand())
    {
        pragma.CommandText = "PRAGMA table_info(AnalysisRecords)";
        using var reader = pragma.ExecuteReader();
        bool hasResultJson = false;
        while (reader.Read())
            if (reader.GetString(1) == "ResultJson") { hasResultJson = true; break; }
        if (!hasResultJson)
        {
            using var alter = conn.CreateCommand();
            alter.CommandText = "ALTER TABLE AnalysisRecords ADD COLUMN ResultJson TEXT";
            alter.ExecuteNonQuery();
            app.Logger.LogInformation("DB migration: added ResultJson column");
        }
    }
    using (var pragma2 = conn.CreateCommand())
    {
        pragma2.CommandText = "PRAGMA table_info(Watchlist)";
        using var reader2 = pragma2.ExecuteReader();
        bool hasSortOrder = false;
        while (reader2.Read())
            if (reader2.GetString(1) == "SortOrder") { hasSortOrder = true; break; }
        if (!hasSortOrder)
        {
            using var alter2 = conn.CreateCommand();
            alter2.CommandText = "ALTER TABLE Watchlist ADD COLUMN SortOrder INTEGER NOT NULL DEFAULT 99";
            alter2.ExecuteNonQuery();
            app.Logger.LogInformation("DB migration: added SortOrder column to Watchlist");
        }
    }
    // UserSettings 表：EnsureCreated 不会给存量库新建表，故手动建（幂等）。
    using (var createSettings = conn.CreateCommand())
    {
        createSettings.CommandText = @"CREATE TABLE IF NOT EXISTS UserSettings (
            Id INTEGER NOT NULL PRIMARY KEY,
            PreMarketEnabled INTEGER NOT NULL,
            PreMarketTime TEXT NOT NULL,
            PostMarketEnabled INTEGER NOT NULL,
            PostMarketTime TEXT NOT NULL,
            LlmProvider TEXT NULL,
            DeepThinkLlm TEXT NULL,
            QuickThinkLlm TEXT NULL,
            UpdatedAt TEXT NOT NULL)";
        createSettings.ExecuteNonQuery();
    }
    conn.Close();

    // 种子单行设置：推送时间用实体默认（08:30/15:10），LLM 默认取 apikeys 的 active_provider
    // 及其模型 → 定时推送开箱即用用户实际配的 provider（而非 DEFAULT_CONFIG 的 openai）。
    if (!db.UserSettings.Any())
    {
        var ak = scope.ServiceProvider.GetRequiredService<Microsoft.Extensions.Options.IOptions<ApiKeysConfig>>().Value;
        var prov = ak.ActiveProvider;
        ApiKeysConfig.ProviderConfig? pc = null;
        if (!string.IsNullOrWhiteSpace(prov)) ak.Providers?.TryGetValue(prov, out pc);
        var llmOk = pc != null && !string.IsNullOrWhiteSpace(pc.ApiKey)
                    && !pc.ApiKey.Contains("REPLACE-ME", StringComparison.OrdinalIgnoreCase);
        db.UserSettings.Add(new TradingPlatform.Api.Models.UserSettings
        {
            Id = 1,
            LlmProvider = llmOk ? prov : null,
            DeepThinkLlm = llmOk ? pc!.DeepThinkModel : null,
            QuickThinkLlm = llmOk ? pc!.QuickThinkModel : null,
        });
        db.SaveChanges();
        app.Logger.LogInformation("已种子 UserSettings 默认行 (llm={Prov})", llmOk ? prov : "(未配,用 DEFAULT_CONFIG)");
    }

    var configWatchlist = app.Configuration.GetSection("Watchlist").Get<List<TradingPlatform.Api.Services.WatchlistItem>>() ?? new();
    if (configWatchlist.Count > 0 && !db.Watchlist.Any())
    {
        foreach (var item in configWatchlist)
        {
            db.Watchlist.Add(new TradingPlatform.Api.Models.WatchlistEntity
            {
                Ticker = item.Ticker.ToUpperInvariant(),
                Name = item.Name,
            });
        }
        db.SaveChanges();
        app.Logger.LogInformation("已从 appsettings.Watchlist 迁移 {Count} 条到数据库", configWatchlist.Count);
    }
}

app.UseSwagger();
app.UseSwaggerUI();

app.UseCors();
app.UseHangfireDashboard("/hangfire", new DashboardOptions
{
    Authorization = Array.Empty<Hangfire.Dashboard.IDashboardAuthorizationFilter>(),
});

app.MapControllers();

app.MapGet("/health", () => Results.Ok(new { status = "ok", time = DateTime.UtcNow }));

app.MapPost("/api/push/test", async (IPushService push, CancellationToken ct) =>
{
    var ok = await push.SendAsync(
        title: "TradingAgents 推送测试",
        markdown: "如果你看到这条消息，说明 Server酱集成正常。\n\n时间: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"),
        ct: ct);
    return Results.Ok(new { success = ok });
});

await HangfireScheduleConfigurer.RegisterRecurringJobsAsync(
    app.Services, app.Configuration, app.Logger);

// Resume any jobs that were in-flight when the API last shut down
var orchestrator = app.Services.GetRequiredService<IAnalysisOrchestrator>();
await orchestrator.ResumeOrphanedJobsAsync();

app.Run();
