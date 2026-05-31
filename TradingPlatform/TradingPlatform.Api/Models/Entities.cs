using System.ComponentModel.DataAnnotations;

namespace TradingPlatform.Api.Models;

public class WatchlistEntity
{
    [Key]
    [MaxLength(32)]
    public string Ticker { get; set; } = string.Empty;

    [MaxLength(128)]
    public string? Name { get; set; }

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
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
