using System.ComponentModel.DataAnnotations;

namespace TradingPlatform.Api.Models;

public class WatchlistEntity
{
    [Key]
    [MaxLength(32)]
    public string Ticker { get; set; } = string.Empty;

    [MaxLength(128)]
    public string? Name { get; set; }

    // Lower = higher priority. 0 runs first (5 min before base schedule), 99 = default.
    public int SortOrder { get; set; } = 99;

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

/// <summary>
/// 全局用户设置（单行，Id 固定为 1；本平台无多用户概念）。
/// 推送时间用 HH:MM + 工作日（UI 友好），注册 Hangfire 时转 cron。
/// LLM 默认 provider/model 应用到定时分析（否则定时任务用 DEFAULT_CONFIG）。
/// 注意：不存任何密钥（Server酱 SendKey/各 LLM api_key 留在 apikeys.local.json，按密钥铁律）。
/// </summary>
public class UserSettings
{
    [Key]
    public int Id { get; set; } = 1;

    public bool PreMarketEnabled { get; set; } = true;
    [MaxLength(5)]
    public string PreMarketTime { get; set; } = "08:30";   // HH:MM，工作日

    public bool PostMarketEnabled { get; set; } = true;
    [MaxLength(5)]
    public string PostMarketTime { get; set; } = "15:10";

    // 默认 false = 分析完不自动推 Server酱，由前端报告页按钮手动推。
    // true = 成功/失败都自动推（含定时任务、Resume 续跑）。
    public bool PushAutoSend { get; set; } = false;

    [MaxLength(32)]
    public string? LlmProvider { get; set; }
    [MaxLength(64)]
    public string? DeepThinkLlm { get; set; }
    [MaxLength(64)]
    public string? QuickThinkLlm { get; set; }

    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}

public class AnalysisRecord
{
    [Key]
    public string JobId { get; set; } = string.Empty;

    [MaxLength(32)]
    public string Ticker { get; set; } = string.Empty;

    [MaxLength(16)]
    public string Date { get; set; } = string.Empty;

    [MaxLength(16)]
    public string Status { get; set; } = string.Empty;

    public string? Decision { get; set; }
    public string? ReportMarkdown { get; set; }
    public string? ResultJson { get; set; }
    public string? Error { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}
