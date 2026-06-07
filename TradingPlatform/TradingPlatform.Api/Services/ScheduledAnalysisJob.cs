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

    // "08:30" → "30 8 * * MON-FRI"（工作日定时）。非法输入兜底到默认盘前时间。
    private static string TimeToCron(string? hhmm)
    {
        var parts = (hhmm ?? "").Split(':');
        if (parts.Length == 2 && int.TryParse(parts[0], out var h) && int.TryParse(parts[1], out var m)
            && h is >= 0 and <= 23 && m is >= 0 and <= 59)
            return $"{m} {h} * * MON-FRI";
        return "30 8 * * MON-FRI";
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

        // 推送时间来源：DB UserSettings 优先（设置页可改），无记录则回退 appsettings Schedule 默认。
        var settings = await db.UserSettings.FindAsync(1);
        var fallback = configuration.GetSection("Schedule").Get<ScheduleOptions>() ?? new();
        var preEnabled = settings?.PreMarketEnabled ?? true;
        var postEnabled = settings?.PostMarketEnabled ?? true;
        var preBaseCron = settings != null ? TimeToCron(settings.PreMarketTime) : fallback.PreMarketCron;
        var postBaseCron = settings != null ? TimeToCron(settings.PostMarketTime) : fallback.PostMarketCron;

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
            var opts = new RecurringJobOptions { TimeZone = TimeZoneInfo.Local };

            if (preEnabled)
                recurring.AddOrUpdate<IScheduledAnalysisJob>(
                    preId, j => j.RunAsync(ticker), ShiftCronEarlier(preBaseCron, minutesEarlier), opts);
            else
                recurring.RemoveIfExists(preId);  // 设置页关掉盘前 → 移除已注册任务

            if (postEnabled)
                recurring.AddOrUpdate<IScheduledAnalysisJob>(
                    postId, j => j.RunAsync(ticker), ShiftCronEarlier(postBaseCron, minutesEarlier), opts);
            else
                recurring.RemoveIfExists(postId);

            logger.LogInformation(
                "注册定时任务 {Ticker} (priority={P}): 盘前 [{Pre}], 盘后 [{Post}]",
                ticker, item.SortOrder,
                preEnabled ? ShiftCronEarlier(preBaseCron, minutesEarlier) : "关",
                postEnabled ? ShiftCronEarlier(postBaseCron, minutesEarlier) : "关");
        }
    }
}
