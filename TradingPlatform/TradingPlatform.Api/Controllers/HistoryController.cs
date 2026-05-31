using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using TradingPlatform.Api.Data;

namespace TradingPlatform.Api.Controllers;

[ApiController]
[Route("api/history")]
public class HistoryController : ControllerBase
{
    private readonly AppDbContext _db;

    public HistoryController(AppDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> List(
        [FromQuery] string? ticker = null,
        [FromQuery] string? from = null,
        [FromQuery] string? to = null,
        [FromQuery] int limit = 100)
    {
        IQueryable<Models.AnalysisRecord> q = _db.AnalysisRecords
            .OrderByDescending(r => r.CreatedAt);

        if (!string.IsNullOrWhiteSpace(ticker))
        {
            ticker = ticker.Trim().ToUpperInvariant();
            q = q.Where(r => r.Ticker == ticker);
        }
        if (DateTime.TryParse(from, out var fromDt))
            q = q.Where(r => r.CreatedAt >= fromDt);
        if (DateTime.TryParse(to, out var toDt))
            q = q.Where(r => r.CreatedAt <= toDt);

        var items = await q
            .Take(Math.Min(limit, 500))
            .Select(r => new
            {
                r.JobId,
                r.Ticker,
                r.Date,
                r.Status,
                r.Decision,
                r.Error,
                r.CreatedAt,
                r.UpdatedAt,
            })
            .ToListAsync();

        return Ok(items);
    }

    [HttpGet("{jobId}")]
    public async Task<IActionResult> Get(string jobId)
    {
        var record = await _db.AnalysisRecords.FindAsync(jobId);
        if (record == null) return NotFound();
        return Ok(record);
    }
}
