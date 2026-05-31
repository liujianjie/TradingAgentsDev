using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using TradingPlatform.Api.Data;
using TradingPlatform.Api.Models;

namespace TradingPlatform.Api.Controllers;

[ApiController]
[Route("api/watchlist")]
public class WatchlistController : ControllerBase
{
    private readonly AppDbContext _db;

    public WatchlistController(AppDbContext db) => _db = db;

    public class WatchlistRequest
    {
        public string Ticker { get; set; } = string.Empty;
        public string? Name { get; set; }
    }

    [HttpGet]
    public async Task<IActionResult> List()
    {
        var items = await _db.Watchlist.OrderBy(w => w.Ticker).ToListAsync();
        return Ok(items);
    }

    [HttpPost]
    public async Task<IActionResult> Add([FromBody] WatchlistRequest body)
    {
        if (string.IsNullOrWhiteSpace(body.Ticker))
            return BadRequest(new { error = "Ticker 不能为空" });

        var ticker = body.Ticker.Trim().ToUpperInvariant();
        var existing = await _db.Watchlist.FindAsync(ticker);
        if (existing != null)
            return Conflict(new { error = $"{ticker} 已在自选股列表" });

        var entity = new WatchlistEntity { Ticker = ticker, Name = body.Name?.Trim() };
        _db.Watchlist.Add(entity);
        await _db.SaveChangesAsync();
        return CreatedAtAction(nameof(List), entity);
    }

    [HttpDelete("{ticker}")]
    public async Task<IActionResult> Remove(string ticker)
    {
        ticker = ticker.Trim().ToUpperInvariant();
        var entity = await _db.Watchlist.FindAsync(ticker);
        if (entity == null) return NotFound();
        _db.Watchlist.Remove(entity);
        await _db.SaveChangesAsync();
        return NoContent();
    }
}
