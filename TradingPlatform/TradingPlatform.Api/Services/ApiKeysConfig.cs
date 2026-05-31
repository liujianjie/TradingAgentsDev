using Microsoft.Extensions.Configuration;

namespace TradingPlatform.Api.Services;

public class ApiKeysConfig
{
    [ConfigurationKeyName("active_provider")]
    public string? ActiveProvider { get; set; }

    [ConfigurationKeyName("providers")]
    public Dictionary<string, ProviderConfig>? Providers { get; set; }

    [ConfigurationKeyName("serverchan")]
    public ServerChanSection? ServerChan { get; set; }

    public class ProviderConfig
    {
        [ConfigurationKeyName("api_key")]
        public string? ApiKey { get; set; }

        [ConfigurationKeyName("deep_think_model")]
        public string? DeepThinkModel { get; set; }

        [ConfigurationKeyName("quick_think_model")]
        public string? QuickThinkModel { get; set; }

        [ConfigurationKeyName("base_url")]
        public string? BaseUrl { get; set; }
    }

    public class ServerChanSection
    {
        [ConfigurationKeyName("send_key")]
        public string? SendKey { get; set; }
    }
}
