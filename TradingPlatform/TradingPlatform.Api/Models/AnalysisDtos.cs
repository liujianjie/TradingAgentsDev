namespace TradingPlatform.Api.Models;

public class AnalysisResult
{
    public string? Decision { get; set; }
    public string? MarketReport { get; set; }
    public string? SentimentReport { get; set; }
    public string? NewsReport { get; set; }
    public string? FundamentalsReport { get; set; }
    public string? InvestmentPlan { get; set; }
    public string? FinalTradeDecision { get; set; }
    // 数据源溯源 markdown 表格（本次各类数据实际命中哪个源/降级了什么）。
    // Python 端 snake_case "data_sources"，经 SnakeCaseLower 策略映射到此属性。
    public string? DataSources { get; set; }
    public string? ReportPath { get; set; }
}

public class AnalysisJob
{
    public string JobId { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string? Ticker { get; set; }
    public string? Date { get; set; }
    public int Progress { get; set; }
    public AnalysisResult? Result { get; set; }
    public string? Error { get; set; }
    public string CreatedAt { get; set; } = string.Empty;
    public string UpdatedAt { get; set; } = string.Empty;
}

public class TriggerResponse
{
    public string JobId { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
}

public class AnalyzeRequest
{
    public string Ticker { get; set; } = string.Empty;
    public string Date { get; set; } = string.Empty;
    public string? LlmProvider { get; set; }
    public string? DeepThinkLlm { get; set; }
    public string? QuickThinkLlm { get; set; }
}

// 设置页读写 DTO（推送时间 + LLM 默认）。不含任何密钥。
public class UserSettingsDto
{
    public bool PreMarketEnabled { get; set; } = true;
    public string PreMarketTime { get; set; } = "08:30";
    public bool PostMarketEnabled { get; set; } = true;
    public string PostMarketTime { get; set; } = "15:10";
    public string? LlmProvider { get; set; }
    public string? DeepThinkLlm { get; set; }
    public string? QuickThinkLlm { get; set; }
}

// 设置页 LLM 下拉用：只列出已配 key 的 provider 及其默认深/快模型（来自 apikeys.local.json）。
public class ProviderInfoDto
{
    public string Provider { get; set; } = string.Empty;
    public string? DeepThinkModel { get; set; }
    public string? QuickThinkModel { get; set; }
}
