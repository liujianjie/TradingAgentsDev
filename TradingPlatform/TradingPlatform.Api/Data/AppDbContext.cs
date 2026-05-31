using Microsoft.EntityFrameworkCore;
using TradingPlatform.Api.Models;

namespace TradingPlatform.Api.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<WatchlistEntity> Watchlist => Set<WatchlistEntity>();
    public DbSet<AnalysisRecord> AnalysisRecords => Set<AnalysisRecord>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<AnalysisRecord>()
            .HasIndex(r => new { r.Ticker, r.CreatedAt });
    }
}
