/**
 * Markdown 渲染 + 交易信号解析。
 * 报告内容来自我们自己的 Python 分析服务（可信源），用 marked 转 HTML 交给 mp-html 渲染。
 */
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

/** 把 markdown 文本转成 HTML 字符串，供 <mp-html :content> 使用 */
export function renderMarkdown(md) {
  if (!md) return ''
  try {
    return marked.parse(String(md))
  } catch {
    // 解析失败时退化为纯文本（保留换行）
    return `<p>${String(md).replace(/\n/g, '<br>')}</p>`
  }
}

/**
 * 从决策文本里解析交易信号。
 * TradingAgents 通常输出 "FINAL TRANSACTION PROPOSAL: **BUY/SELL/HOLD**"。
 * 返回 { key, label, } 之一或 null。
 */
export function parseSignal(text) {
  if (!text) return null
  const t = String(text).toUpperCase()
  // 优先匹配最终提案后面的词
  const m = t.match(/PROPOSAL[:：]?\s*\*{0,2}(BUY|SELL|HOLD)/)
  const word = m ? m[1] : null
  if (word === 'SELL' || (!word && /\bSELL\b|卖出|减持|看空/.test(t))) {
    return { key: 'sell', label: '卖出' }
  }
  if (word === 'BUY' || (!word && /\bBUY\b|买入|加仓|看多/.test(t))) {
    return { key: 'buy', label: '买入' }
  }
  if (word === 'HOLD' || (!word && /\bHOLD\b|持有|观望|中性/.test(t))) {
    return { key: 'hold', label: '持有' }
  }
  return null
}
