using TradingPlatform.Api.Models;

namespace TradingPlatform.Api.Services;

public interface IAnalysisService
{
    Task<string> TriggerAsync(AnalyzeRequest request, CancellationToken ct = default);
    Task<AnalysisJob> GetJobAsync(string jobId, CancellationToken ct = default);
    Task<AnalysisJob> WaitForCompletionAsync(string jobId, CancellationToken ct = default);
}
