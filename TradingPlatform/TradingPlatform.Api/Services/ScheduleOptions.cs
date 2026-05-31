namespace TradingPlatform.Api.Services;

public class WatchlistItem
{
    public string Ticker { get; set; } = string.Empty;
    public string? Name { get; set; }
}

public class ScheduleOptions
{
    public string PreMarketCron { get; set; } = "30 8 * * MON-FRI";
    public string PostMarketCron { get; set; } = "10 15 * * MON-FRI";
}
