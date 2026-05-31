using Hangfire;
using Microsoft.EntityFrameworkCore;
using TradingPlatform.Api.Data;

namespace TradingPlatform.Api.Services;

public interface IScheduledAnalysisJob
{
    Task RunAsync(string ticker);
}

public class ScheduledAnalysisJob : IScheduledAnalysisJob
{
    private readonly IAnalysisOrchestrator _orchestrator;
    private readonly ILogger<ScheduledAnalysisJob> _logger;

    public ScheduledAnalysisJob(IAnalysisOrchestrator orchestrator, ILogger<ScheduledAnalysisJob> logger)
    {
        _orchestrator = orchestrator;
        _logger = logger;
    }

    public async Task RunAsync(string ticker)
    {
        var date = DateTime.UtcNow.ToString("yyyy-MM-dd");
        _logger.LogInformation("定时触发 {Ticker} 分析 (date={Date})", ticker, date);
        await _orchestrator.TriggerAndPushAsync(ticker, date);
    }
}

public static class HangfireScheduleConfigurer
{
    public static async Task RegisterRecurringJobsAsync(
        IServiceProvider services,
        IConfiguration configuration,
        ILogger logger)
    {
        using var scope = services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var recurring = scope.ServiceProvider.GetRequiredService<IRecurringJobManager>();

        var watchlist = await db.Watchlist.ToListAsync();
        var schedule = configuration.GetSection("Schedule").Get<ScheduleOptions>() ?? new();

        if (watchlist.Count == 0)
        {
            logger.LogWarning("Watchlist 为空（数据库中无记录），未注册任何定时任务");
            return;
        }

        foreach (var item in watchlist)
        {
            var preId = $"premarket-{item.Ticker}";
            var postId = $"postmarket-{item.Ticker}";
            var ticker = item.Ticker;

            recurring.AddOrUpdate<IScheduledAnalysisJob>(
                preId, j => j.RunAsync(ticker), schedule.PreMarketCron, new RecurringJobOptions
                {
                    TimeZone = TimeZoneInfo.Local,
                });
            recurring.AddOrUpdate<IScheduledAnalysisJob>(
                postId, j => j.RunAsync(ticker), schedule.PostMarketCron, new RecurringJobOptions
                {
                    TimeZone = TimeZoneInfo.Local,
                });
            logger.LogInformation(
                "注册定时任务 {Ticker}: 盘前 [{PreCron}], 盘后 [{PostCron}]",
                ticker, schedule.PreMarketCron, schedule.PostMarketCron);
        }
    }
}
