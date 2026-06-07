using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Options;
using TradingPlatform.Api.Models;

namespace TradingPlatform.Api.Services;

public class PythonApiOptions
{
    public string BaseUrl { get; set; } = "http://localhost:28100";
    public int PollIntervalSeconds { get; set; } = 10;
    public int TimeoutMinutes { get; set; } = 60;
}

public class AnalysisService : IAnalysisService
{
    private readonly HttpClient _http;
    private readonly PythonApiOptions _options;
    private readonly ILogger<AnalysisService> _logger;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    public AnalysisService(
        HttpClient http,
        IOptions<PythonApiOptions> options,
        ILogger<AnalysisService> logger)
    {
        _http = http;
        _options = options.Value;
        _logger = logger;
        _http.BaseAddress = new Uri(_options.BaseUrl);
        _http.Timeout = TimeSpan.FromMinutes(2);
    }

    public async Task<string> TriggerAsync(AnalyzeRequest request, CancellationToken ct = default)
    {
        var resp = await _http.PostAsJsonAsync("/api/v1/analyze", request, JsonOpts, ct);
        resp.EnsureSuccessStatusCode();
        var body = await resp.Content.ReadFromJsonAsync<TriggerResponse>(JsonOpts, ct)
            ?? throw new InvalidOperationException("Python API 返回空响应");
        _logger.LogInformation("已触发分析: {Ticker} {Date} → {JobId}", request.Ticker, request.Date, body.JobId);
        return body.JobId;
    }

    public async Task<AnalysisJob> GetJobAsync(string jobId, CancellationToken ct = default)
    {
        var resp = await _http.GetAsync($"/api/v1/jobs/{jobId}", ct);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<AnalysisJob>(JsonOpts, ct)
            ?? throw new InvalidOperationException($"Job {jobId} 返回空响应");
    }

    public async Task<AnalysisJob> WaitForCompletionAsync(string jobId, CancellationToken ct = default)
    {
        var deadline = DateTime.UtcNow.AddMinutes(_options.TimeoutMinutes);
        while (DateTime.UtcNow < deadline)
        {
            ct.ThrowIfCancellationRequested();
            var job = await GetJobAsync(jobId, ct);
            if (job.Status is "completed" or "failed")
            {
                _logger.LogInformation("Job {JobId} 终态: {Status}", jobId, job.Status);
                return job;
            }
            await Task.Delay(TimeSpan.FromSeconds(_options.PollIntervalSeconds), ct);
        }
        throw new TimeoutException($"Job {jobId} 在 {_options.TimeoutMinutes} 分钟内未完成");
    }
}
