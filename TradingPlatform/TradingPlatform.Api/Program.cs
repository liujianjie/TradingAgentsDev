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
    conn.Close();

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
