namespace TradingPlatform.Api.Services;

public interface IPushService
{
    Task<bool> SendAsync(string title, string markdown, CancellationToken ct = default);
}
