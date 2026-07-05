using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using TradingPlatform.Api.Data;
using TradingPlatform.Api.Models;
using TradingPlatform.Api.Services;

namespace TradingPlatform.Api.Controllers;

[ApiController]
[Route("api/analysis")]
public class AnalysisController : ControllerBase
{
    private readonly IAnalysisOrchestrator _orchestrator;
    private readonly IAnalysisService _analysis;
    private readonly AppDbContext _db;
    private readonly IPushService _push;
    private readonly ILogger<AnalysisController> _logger;

    public AnalysisController(
        IAnalysisOrchestrator orchestrator,
        IAnalysisService analysis,
        AppDbContext db,
        IPushService push,
        ILogger<AnalysisController> logger)
    {
        _orchestrator = orchestrator;
        _analysis = analysis;
        _db = db;
        _push = push;
        _logger = logger;
    }

    public class TriggerBody
    {
        public string Ticker { get; set; } = string.Empty;
        public string? Date { get; set; }
    }

    [HttpPost("trigger")]
    public async Task<IActionResult> Trigger([FromBody] TriggerBody body, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(body.Ticker))
            return BadRequest(new { error = "Ticker 不能为空" });

        var date = string.IsNullOrWhiteSpace(body.Date)
            ? DateTime.UtcNow.ToString("yyyy-MM-dd")
            : body.Date;

        try
        {
            var jobId = await _orchestrator.TriggerAndPushAsync(body.Ticker, date, ct);
            return Ok(new { jobId, ticker = body.Ticker, date });
        }
        catch (HttpRequestException ex)
        {
            return StatusCode(503, new { error = "Python 分析服务不可用", detail = ex.Message });
        }
    }

    [HttpGet("jobs/{jobId}")]
    public async Task<IActionResult> GetJob(string jobId, CancellationToken ct)
    {
        // For terminal states serve from DB — survives Python API restarts
        var record = await _db.AnalysisRecords.FindAsync(new object[] { jobId }, ct);
        if (record != null && (record.Status == "completed" || record.Status == "failed"))
        {
            var result = record.ResultJson != null
                ? JsonSerializer.Deserialize<AnalysisResult>(record.ResultJson,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
                : null;
            return Ok(new AnalysisJob
            {
                JobId = record.JobId,
                Status = record.Status,
                Ticker = record.Ticker,
                Date = record.Date,
                Progress = record.Status == "completed" ? 100 : 5,
                Result = result,
                Error = record.Error,
                CreatedAt = record.CreatedAt.ToString("o"),
                UpdatedAt = record.UpdatedAt.ToString("o"),
            });
        }

        // In-flight: forward to Python
        var job = await _analysis.GetJobAsync(jobId, ct);
        return Ok(job);
    }

    /// <summary>
    /// 手动推已完成的分析报告到 Server酱（前端报告页"📲 推送到手机"按钮）。
    /// 与设置页"自动推送"开关解耦：开关关时也能手动推单条。
    /// </summary>
    [HttpPost("jobs/{jobId}/push")]
    public async Task<IActionResult> PushJob(string jobId, CancellationToken ct)
    {
        var record = await _db.AnalysisRecords.FindAsync(new object[] { jobId }, ct);
        if (record == null)
            return NotFound(new { error = "任务不存在" });
        if (record.Status != "completed" || string.IsNullOrWhiteSpace(record.ReportMarkdown))
            return BadRequest(new { error = "仅已完成的分析报告可手动推送", status = record.Status });

        var title = ReportFormatter.BuildTitle(record.Ticker, record.Decision);
        var ok = await _push.SendAsync(title, record.ReportMarkdown, ct);
        if (!ok)
        {
            _logger.LogWarning("手动推送失败 {JobId} {Ticker}", jobId, record.Ticker);
            return StatusCode(502, new { success = false, error = "推送服务返回失败（检查 Server酱 SendKey / 配额）" });
        }
        return Ok(new { success = true });
    }
}
