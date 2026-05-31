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

    public AnalysisController(IAnalysisOrchestrator orchestrator, IAnalysisService analysis, AppDbContext db)
    {
        _orchestrator = orchestrator;
        _analysis = analysis;
        _db = db;
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
}
