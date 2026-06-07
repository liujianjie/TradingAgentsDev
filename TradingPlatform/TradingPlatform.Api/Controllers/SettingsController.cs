using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using TradingPlatform.Api.Data;
using TradingPlatform.Api.Models;
using TradingPlatform.Api.Services;

namespace TradingPlatform.Api.Controllers;

/// <summary>
/// 全局设置：推送时间 + LLM 默认模型（单行配置，无多用户）。
/// 不经手任何密钥——provider 是否可用由 apikeys.local.json 是否配 key 决定（见 GetProviders）。
/// </summary>
[ApiController]
[Route("api/settings")]
public class SettingsController : ControllerBase
{
    private readonly AppDbContext _db;
    private readonly IOptions<ApiKeysConfig> _apiKeys;
    private readonly IServiceProvider _services;
    private readonly IConfiguration _config;
    private readonly ILogger<SettingsController> _logger;

    public SettingsController(
        AppDbContext db,
        IOptions<ApiKeysConfig> apiKeys,
        IServiceProvider services,
        IConfiguration config,
        ILogger<SettingsController> logger)
    {
        _db = db;
        _apiKeys = apiKeys;
        _services = services;
        _config = config;
        _logger = logger;
    }

    [HttpGet]
    public async Task<IActionResult> Get(CancellationToken ct)
    {
        var s = await _db.UserSettings.FindAsync(new object[] { 1 }, ct);
        return Ok(ToDto(s));
    }

    [HttpPost]
    public async Task<IActionResult> Update([FromBody] UserSettingsDto dto, CancellationToken ct)
    {
        if (!IsValidTime(dto.PreMarketTime) || !IsValidTime(dto.PostMarketTime))
            return BadRequest(new { error = "时间格式须为 HH:MM（24 小时制）" });

        var s = await _db.UserSettings.FindAsync(new object[] { 1 }, ct);
        if (s == null)
        {
            s = new UserSettings { Id = 1 };
            _db.UserSettings.Add(s);
        }
        s.PreMarketEnabled = dto.PreMarketEnabled;
        s.PreMarketTime = dto.PreMarketTime;
        s.PostMarketEnabled = dto.PostMarketEnabled;
        s.PostMarketTime = dto.PostMarketTime;
        s.LlmProvider = NullIfBlank(dto.LlmProvider);
        s.DeepThinkLlm = NullIfBlank(dto.DeepThinkLlm);
        s.QuickThinkLlm = NullIfBlank(dto.QuickThinkLlm);
        s.UpdatedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync(ct);

        // 推送时间改了 → 立即热更新 Hangfire 定时任务（按新时间重注册）
        await HangfireScheduleConfigurer.RegisterRecurringJobsAsync(_services, _config, _logger);
        _logger.LogInformation("用户设置已更新并重注册定时任务");

        return Ok(ToDto(s));
    }

    /// <summary>列出 apikeys.local.json 里真正配了 key 的 provider（避免用户选了没 key 的源→分析白跑）。</summary>
    [HttpGet("providers")]
    public IActionResult GetProviders()
    {
        var list = new List<ProviderInfoDto>();
        foreach (var (name, cfg) in _apiKeys.Value.Providers ?? new())
        {
            if (IsConfigured(cfg?.ApiKey))
                list.Add(new ProviderInfoDto
                {
                    Provider = name,
                    DeepThinkModel = cfg!.DeepThinkModel,
                    QuickThinkModel = cfg.QuickThinkModel,
                });
        }
        return Ok(list);
    }

    private static bool IsConfigured(string? key)
        => !string.IsNullOrWhiteSpace(key) && !key.Contains("REPLACE-ME", StringComparison.OrdinalIgnoreCase);

    private static bool IsValidTime(string? hhmm)
        => !string.IsNullOrWhiteSpace(hhmm)
           && TimeOnly.TryParseExact(hhmm, "HH:mm", out _);

    private static string? NullIfBlank(string? s)
        => string.IsNullOrWhiteSpace(s) ? null : s.Trim();

    private static UserSettingsDto ToDto(UserSettings? s)
        => s == null
            ? new UserSettingsDto()
            : new UserSettingsDto
            {
                PreMarketEnabled = s.PreMarketEnabled,
                PreMarketTime = s.PreMarketTime,
                PostMarketEnabled = s.PostMarketEnabled,
                PostMarketTime = s.PostMarketTime,
                LlmProvider = s.LlmProvider,
                DeepThinkLlm = s.DeepThinkLlm,
                QuickThinkLlm = s.QuickThinkLlm,
            };
}
