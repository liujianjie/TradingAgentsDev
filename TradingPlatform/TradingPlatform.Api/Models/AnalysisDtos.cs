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
