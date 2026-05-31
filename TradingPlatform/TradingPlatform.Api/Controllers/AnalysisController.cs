using Microsoft.AspNetCore.Mvc;
using TradingPlatform.Api.Services;

namespace TradingPlatform.Api.Controllers;

[ApiController]
[Route("api/analysis")]
public class AnalysisController : ControllerBase
{
    private readonly IAnalysisOrchestrator _orchestrator;
    private readonly IAnalysisService _analysis;

    public AnalysisController(IAnalysisOrchestrator orchestrator, IAnalysisService analysis)
    {
        _orchestrator = orchestrator;
        _analysis = analysis;
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
        var job = await _analysis.GetJobAsync(jobId, ct);
        return Ok(job);
    }
}
