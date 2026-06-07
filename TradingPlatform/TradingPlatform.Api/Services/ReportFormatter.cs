using System.Text;
using TradingPlatform.Api.Models;

namespace TradingPlatform.Api.Services;

public static class ReportFormatter
{
    public static (string Title, string Markdown) Format(string ticker, AnalysisJob job)
    {
        if (job.Status == "failed")
        {
            return (
                $"分析失败: {ticker}",
                $"## 分析失败\n\n**Ticker**: {ticker}\n**时间**: {job.UpdatedAt}\n\n**错误**:\n```\n{job.Error}\n```"
            );
        }

        var r = job.Result ?? new AnalysisResult();
        var sb = new StringBuilder();

        sb.AppendLine($"## {ticker} | 分析报告");
        sb.AppendLine();
        sb.AppendLine($"**日期**: {job.Date}  ");
        sb.AppendLine($"**完成时间**: {job.UpdatedAt}");
        sb.AppendLine();

        if (!string.IsNullOrWhiteSpace(r.FinalTradeDecision))
        {
            sb.AppendLine("### 最终决策");
            sb.AppendLine(Trim(r.FinalTradeDecision, 2000));
            sb.AppendLine();
        }

        if (!string.IsNullOrWhiteSpace(r.InvestmentPlan))
        {
            sb.AppendLine("### 投资计划");
            sb.AppendLine(Trim(r.InvestmentPlan, 1500));
            sb.AppendLine();
        }

        AppendSection(sb, "技术面分析", r.MarketReport, 1500);
        AppendSection(sb, "情感面分析", r.SentimentReport, 1000);
        AppendSection(sb, "新闻面分析", r.NewsReport, 1500);
        AppendSection(sb, "基本面分析", r.FundamentalsReport, 1500);
        AppendSection(sb, "数据源溯源", r.DataSources, 800);

        var title = BuildTitle(ticker, r.Decision);
        return (title, sb.ToString());
    }

    private static void AppendSection(StringBuilder sb, string heading, string? body, int max)
    {
        if (string.IsNullOrWhiteSpace(body)) return;
        sb.AppendLine($"### {heading}");
        sb.AppendLine(Trim(body, max));
        sb.AppendLine();
    }

    private static string Trim(string s, int max)
        => s.Length <= max ? s : s[..max] + "...(略)";

    private static string BuildTitle(string ticker, string? decision)
    {
        if (string.IsNullOrWhiteSpace(decision))
            return $"[TradingAgents] {ticker} 分析完成";

        var d = decision.ToUpperInvariant();
        var emoji = d.Contains("BUY") ? "🟢"
                  : d.Contains("SELL") ? "🔴"
                  : "🟡";
        return $"{emoji} {ticker} {decision}";
    }
}
