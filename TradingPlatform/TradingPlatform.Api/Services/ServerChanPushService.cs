using Microsoft.Extensions.Options;

namespace TradingPlatform.Api.Services;

public class ServerChanOptions
{
    public string SendKey { get; set; } = string.Empty;
}

public class ServerChanPushService : IPushService
{
    private readonly HttpClient _http;
    private readonly ILogger<ServerChanPushService> _logger;
    private readonly string _sendKey;

    public ServerChanPushService(
        HttpClient http,
        IOptions<ApiKeysConfig> apiKeys,
        IOptions<ServerChanOptions> fallback,
        ILogger<ServerChanPushService> logger)
    {
        _http = http;
        _logger = logger;

        var fromApiKeys = apiKeys.Value.ServerChan?.SendKey;
        var fromAppSettings = fallback.Value.SendKey;
        var fromEnv = Environment.GetEnvironmentVariable("SERVERCHAN_SEND_KEY");

        _sendKey = !string.IsNullOrWhiteSpace(fromApiKeys) ? fromApiKeys
                 : !string.IsNullOrWhiteSpace(fromEnv) ? fromEnv
                 : fromAppSettings ?? string.Empty;
    }

    public async Task<bool> SendAsync(string title, string markdown, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(_sendKey))
        {
            _logger.LogWarning("Server酱 SendKey 未配置 (config/apikeys.local.json → serverchan.send_key)");
            return false;
        }

        var url = $"https://sctapi.ftqq.com/{_sendKey}.send";
        var form = new FormUrlEncodedContent(new[]
        {
            new KeyValuePair<string, string>("title", title),
            new KeyValuePair<string, string>("desp", markdown),
        });

        try
        {
            using var resp = await _http.PostAsync(url, form, ct);
            var body = await resp.Content.ReadAsStringAsync(ct);
            if (!resp.IsSuccessStatusCode)
            {
                _logger.LogError("Server酱推送失败 {Status}: {Body}", resp.StatusCode, body);
                return false;
            }
            _logger.LogInformation("Server酱推送成功: {Title}", title);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Server酱推送异常");
            return false;
        }
    }
}
