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
    // Shift a "M H * * *" cron earlier by N minutes. Wraps around hour boundary.
    private static string ShiftCronEarlier(string cron, int minutesBefore)
    {
        if (minutesBefore <= 0) return cron;
        var parts = cron.Split(' ');
        if (parts.Length < 2 || !int.TryParse(parts[0], out var minute) || !int.TryParse(parts[1], out var hour))
            return cron;
        minute -= minutesBefore;
        if (minute < 0) { minute += 60; hour = (hour - 1 + 24) % 24; }
        parts[0] = minute.ToString();
        parts[1] = hour.ToString();
        return string.Join(' ', parts);
    }

    public static async Task RegisterRecurringJobsAsync(
        IServiceProvider services,
        IConfiguration configuration,
        ILogger logger)
    {
        using var scope = services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var recurring = scope.ServiceProvider.GetRequiredService<IRecurringJobManager>();

        var watchlist = await db.Watchlist.OrderBy(w => w.SortOrder).ThenBy(w => w.Ticker).ToListAsync();
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

            // Priority items (SortOrder < 10) fire 5 min before the base schedule
            var minutesEarlier = item.SortOrder < 10 ? 5 : 0;
            var preCron = ShiftCronEarlier(schedule.PreMarketCron, minutesEarlier);
            var postCron = ShiftCronEarlier(schedule.PostMarketCron, minutesEarlier);

            recurring.AddOrUpdate<IScheduledAnalysisJob>(
                preId, j => j.RunAsync(ticker), preCron, new RecurringJobOptions
                {
                    TimeZone = TimeZoneInfo.Local,
                });
            recurring.AddOrUpdate<IScheduledAnalysisJob>(
                postId, j => j.RunAsync(ticker), postCron, new RecurringJobOptions
                {
                    TimeZone = TimeZoneInfo.Local,
                });
            logger.LogInformation(
                "注册定时任务 {Ticker} (priority={P}): 盘前 [{PreCron}], 盘后 [{PostCron}]",
                ticker, item.SortOrder, preCron, postCron);
        }
    }
}
