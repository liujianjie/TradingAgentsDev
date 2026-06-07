using System.Text.Json;
using TradingPlatform.Api.Data;
using TradingPlatform.Api.Models;

namespace TradingPlatform.Api.Services;

public interface IAnalysisOrchestrator
{
    Task<string> TriggerAndPushAsync(string ticker, string date, CancellationToken ct = default);
    Task ResumeOrphanedJobsAsync();
}

public class AnalysisOrchestrator : IAnalysisOrchestrator
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<AnalysisOrchestrator> _logger;
    private readonly string _reportsDir;

    public AnalysisOrchestrator(
        IServiceScopeFactory scopeFactory,
        ILogger<AnalysisOrchestrator> logger,
        IHostEnvironment env)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
        _reportsDir = Path.GetFullPath(Path.Combine(env.ContentRootPath, "../../reports"));
    }

    private async Task<string> SaveReportAsync(string ticker, string? date, string jobId, string markdown)
    {
        Directory.CreateDirectory(_reportsDir);
        var safeDate = (date ?? DateTime.UtcNow.ToString("yyyy-MM-dd")).Replace("/", "-");
        var fileName = $"{ticker}_{safeDate}_{jobId[..8]}.md";
        var path = Path.Combine(_reportsDir, fileName);
        await File.WriteAllTextAsync(path, markdown, System.Text.Encoding.UTF8);
        return path;
    }

    public async Task<string> TriggerAndPushAsync(string ticker, string date, CancellationToken ct = default)
    {
        // 先创建一个本地 record（pending jobId），保证 history 总能记录到
        var localId = Guid.NewGuid().ToString("N");
        using (var scope = _scopeFactory.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            db.AnalysisRecords.Add(new AnalysisRecord
            {
                JobId = localId,
                Ticker = ticker,
                Date = date,
                Status = "queued",
            });
            await db.SaveChangesAsync(ct);
        }

        // 尝试触发 Python；失败则更新 record 为 failed
        string pythonJobId;
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var analysis = scope.ServiceProvider.GetRequiredService<IAnalysisService>();
            pythonJobId = await analysis.TriggerAsync(
                new AnalyzeRequest { Ticker = ticker, Date = date }, ct);

            // 把 Python 的 jobId 关联到 record（jobId 字段更新为 Python 的 ID）
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            var record = await db.AnalysisRecords.FindAsync(new object[] { localId }, ct);
            if (record != null)
            {
                db.AnalysisRecords.Remove(record);
                db.AnalysisRecords.Add(new AnalysisRecord
                {
                    JobId = pythonJobId,
                    Ticker = record.Ticker,
                    Date = record.Date,
                    Status = "queued",
                    CreatedAt = record.CreatedAt,
                });
                await db.SaveChangesAsync(ct);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "触发 Python 分析失败 {Ticker}", ticker);
            using var scope = _scopeFactory.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            var record = await db.AnalysisRecords.FindAsync(new object[] { localId }, ct);
            if (record != null)
            {
                record.Status = "failed";
                record.Error = "无法触发 Python 服务: " + ex.Message;
                record.UpdatedAt = DateTime.UtcNow;
                await db.SaveChangesAsync(ct);
            }
            throw;
        }

        // 后台等待 + 推送
        var jobIdForBg = pythonJobId;
        var tickerForBg = ticker;
        _ = Task.Run(async () =>
        {
            using var scope = _scopeFactory.CreateScope();
            var analysis = scope.ServiceProvider.GetRequiredService<IAnalysisService>();
            var push = scope.ServiceProvider.GetRequiredService<IPushService>();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

            try
            {
                var job = await analysis.WaitForCompletionAsync(jobIdForBg, CancellationToken.None);
                var (title, markdown) = ReportFormatter.Format(tickerForBg, job);

                if (job.Result != null && job.Status == "completed")
                    job.Result.ReportPath = await SaveReportAsync(tickerForBg, job.Date, jobIdForBg, markdown);

                var record = await db.AnalysisRecords.FindAsync(jobIdForBg);
                if (record != null)
                {
                    record.Status = job.Status;
                    record.Decision = job.Result?.Decision;
                    record.ReportMarkdown = markdown;
                    record.ResultJson = job.Result != null ? JsonSerializer.Serialize(job.Result) : null;
                    record.Error = job.Error;
                    record.UpdatedAt = DateTime.UtcNow;
                    await db.SaveChangesAsync();
                }

                await push.SendAsync(title, markdown, CancellationToken.None);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "编排失败 {Ticker} {JobId}", tickerForBg, jobIdForBg);

                var record = await db.AnalysisRecords.FindAsync(jobIdForBg);
                if (record != null)
                {
                    record.Status = "failed";
                    record.Error = ex.Message;
                    record.UpdatedAt = DateTime.UtcNow;
                    await db.SaveChangesAsync();
                }

                await push.SendAsync(
                    $"分析异常: {tickerForBg}",
                    $"## 编排失败\n\n**Ticker**: {tickerForBg}\n\n**异常**:\n```\n{ex.Message}\n```",
                    CancellationToken.None);
            }
        }, CancellationToken.None);

        return pythonJobId;
    }

    public async Task ResumeOrphanedJobsAsync()
    {
        using var scope = _scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var orphans = db.AnalysisRecords
            .Where(r => r.Status == "queued" || r.Status == "running")
            .ToList();

        if (orphans.Count == 0) return;

        _logger.LogInformation("Resuming {Count} orphaned job(s) after restart", orphans.Count);
        foreach (var record in orphans)
        {
            var jobId = record.JobId;
            var ticker = record.Ticker;
            _ = Task.Run(async () =>
            {
                using var s = _scopeFactory.CreateScope();
                var analysis = s.ServiceProvider.GetRequiredService<IAnalysisService>();
                var push = s.ServiceProvider.GetRequiredService<IPushService>();
                var dbInner = s.ServiceProvider.GetRequiredService<AppDbContext>();
                try
                {
                    var job = await analysis.WaitForCompletionAsync(jobId, CancellationToken.None);
                    var (title, markdown) = ReportFormatter.Format(ticker, job);

                    if (job.Result != null && job.Status == "completed")
                        job.Result.ReportPath = await SaveReportAsync(ticker, job.Date, jobId, markdown);

                    var r = await dbInner.AnalysisRecords.FindAsync(jobId);
                    if (r != null)
                    {
                        r.Status = job.Status;
                        r.Decision = job.Result?.Decision;
                        r.ReportMarkdown = markdown;
                        r.ResultJson = job.Result != null ? JsonSerializer.Serialize(job.Result) : null;
                        r.Error = job.Error;
                        r.UpdatedAt = DateTime.UtcNow;
                        await dbInner.SaveChangesAsync();
                    }
                    await push.SendAsync(title, markdown, CancellationToken.None);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Resume orphan failed {JobId}", jobId);
                    var r = await dbInner.AnalysisRecords.FindAsync(jobId);
                    if (r != null) { r.Status = "failed"; r.Error = ex.Message; r.UpdatedAt = DateTime.UtcNow; await dbInner.SaveChangesAsync(); }
                }
            });
        }
    }
}
