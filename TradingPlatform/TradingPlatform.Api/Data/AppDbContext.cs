using Microsoft.EntityFrameworkCore;
using TradingPlatform.Api.Models;

namespace TradingPlatform.Api.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<WatchlistEntity> Watchlist => Set<WatchlistEntity>();
    public DbSet<AnalysisRecord> AnalysisRecords => Set<AnalysisRecord>();
    public DbSet<UserSettings> UserSettings => Set<UserSettings>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<AnalysisRecord>()
            .HasIndex(r => new { r.Ticker, r.CreatedAt });

        // 单行设置：Id 固定为 1，非自增（否则 EF 默认把 int 主键当 identity，显式 Id=1 会被覆盖）
        modelBuilder.Entity<UserSettings>()
            .Property(s => s.Id).ValueGeneratedNever();
    }
}
