const KOREAN_COMPANIES = new Set(['sk_hynix', 'samsung'])
const CHART_ORDER = [
  'sandisk_all',
  'micron_all',
  'sk_hynix_all',
  'sk_hynix_kr',
  'samsung_all',
  'samsung_kr',
  'kioxia_all',
]
const CHART_RANK = new Map(CHART_ORDER.map((id, index) => [id, index]))


export function displayCompanyName(value) {
  return typeof value === 'string'
    ? value.replace(/\s+\((all|kr)\)$/i, '')
    : ''
}


export function selectMemorySeries(series, scope) {
  if (!Array.isArray(series)) return []
  if (scope !== 'kr') return series.filter(item => item.scope === 'all')
  return series.filter(item => {
    if (KOREAN_COMPANIES.has(item.company_id)) return item.scope === 'kr'
    return item.scope === 'all'
  })
}


export function selectChartSeries(series) {
  if (!Array.isArray(series)) return []
  return series
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftRank = CHART_RANK.get(left.item.id) ?? CHART_ORDER.length + left.index
      const rightRank = CHART_RANK.get(right.item.id) ?? CHART_ORDER.length + right.index
      return leftRank - rightRank
    })
    .map(entry => entry.item)
}


export function chartLinePattern(item) {
  if (item?.company_id === 'kioxia') return [2, 4]
  if (item?.scope === 'kr') return [7, 5]
  return []
}


export function formatRatio(value) {
  return Number.isFinite(value) ? value.toFixed(3) : '—'
}


export function formatPercent(value) {
  return Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'
}


function compact(value, divisor, suffix, digits) {
  const number = Number((value / divisor).toFixed(digits))
  return `$${number}${suffix}`
}


export function formatUsd(value) {
  if (!Number.isFinite(value)) return '—'
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000_000) return compact(value, 1_000_000_000, 'B', 2)
  if (absolute >= 1_000_000) return compact(value, 1_000_000, 'M', 0)
  if (absolute >= 1_000) return compact(value, 1_000, 'K', 0)
  return `$${Math.round(value)}`
}


export function leverageMetrics(latest) {
  const longTurnoverUsd = Number.isFinite(latest?.long_turnover_usd)
    ? latest.long_turnover_usd
    : 0
  const shortTurnoverUsd = Number.isFinite(latest?.short_turnover_usd)
    ? latest.short_turnover_usd
    : 0
  const totalTurnoverUsd = longTurnoverUsd + shortTurnoverUsd

  return {
    totalTurnoverUsd,
    longShare: totalTurnoverUsd > 0 ? longTurnoverUsd / totalTurnoverUsd : null,
    shortShare: totalTurnoverUsd > 0 ? shortTurnoverUsd / totalTurnoverUsd : null,
  }
}


export function leverageProductCount(coverage, item) {
  if (!Array.isArray(coverage) || !item?.company_id) return 0
  return coverage.filter(row =>
    row.company_id === item.company_id
    && row.role === 'leveraged'
    && row.status === 'ok'
    && (item.scope !== 'kr' || row.venue === 'KRX')
  ).length
}


function niceStep(value) {
  if (!Number.isFinite(value) || value <= 0) return 0.1
  const exponent = 10 ** Math.floor(Math.log10(value))
  const fraction = value / exponent
  const niceFraction = fraction <= 1
    ? 1
    : fraction <= 2
      ? 2
      : fraction <= 2.5
        ? 2.5
        : fraction <= 5
          ? 5
          : 10
  return niceFraction * exponent
}


export function chartDomain(series) {
  const points = (series || [])
    .flatMap(item => item.points || [])
    .map(point => ({ time: Date.parse(point.date), ratio: Number(point.ratio) }))
    .filter(point => Number.isFinite(point.time) && Number.isFinite(point.ratio) && point.ratio >= 0)
  if (!points.length) return null
  const times = points.map(point => point.time)
  const ratios = points.map(point => point.ratio)
  const rawMax = Math.max(...ratios)
  const step = niceStep(rawMax / 7)
  let maxRatio = Math.max(step, Math.ceil(rawMax / step) * step)
  if (rawMax / maxRatio > 0.98) maxRatio += step
  return {
    minTime: Math.min(...times),
    maxTime: Math.max(...times),
    maxRatio: Number(maxRatio.toFixed(6)),
  }
}


export function chartYAxisTicks(maxRatio, maxIntervals = 7) {
  if (!Number.isFinite(maxRatio) || maxRatio <= 0) return []
  const step = niceStep(maxRatio / Math.max(3, maxIntervals))
  const ticks = []
  for (let value = 0; value < maxRatio && ticks.length <= maxIntervals; value += step) {
    ticks.push(Number(value.toFixed(10)))
  }
  if (ticks.at(-1) !== maxRatio) ticks.push(maxRatio)
  return ticks
}


export function chartMonthTicks(series, maxTicks = 7) {
  const times = (series || [])
    .flatMap(item => item.points || [])
    .map(point => Date.parse(point.date))
    .filter(Number.isFinite)
  if (!times.length) return []

  const minTime = Math.min(...times)
  const maxTime = Math.max(...times)
  const minDate = new Date(minTime)
  const cursor = new Date(Date.UTC(minDate.getUTCFullYear(), minDate.getUTCMonth(), 1))
  const months = []
  while (cursor.getTime() <= maxTime) {
    months.push({
      time: Math.max(cursor.getTime(), minTime),
      label: `${cursor.getUTCMonth() + 1}月`,
    })
    cursor.setUTCMonth(cursor.getUTCMonth() + 1)
  }

  const stride = Math.max(1, Math.ceil(months.length / Math.max(1, maxTicks)))
  const sampled = months.filter((_, index) => index % stride === 0)
  const finalMonth = months.at(-1)
  if (finalMonth && sampled.at(-1)?.label !== finalMonth.label) {
    if (sampled.length >= maxTicks) sampled[sampled.length - 1] = finalMonth
    else sampled.push(finalMonth)
  }
  return sampled
}


export function layoutEndLabels(series, maxRatio, plotHeight, minGap = 16) {
  if (!Number.isFinite(maxRatio) || maxRatio <= 0 || plotHeight <= 0) return []
  const labels = (series || [])
    .filter(item => Number.isFinite(item.latest?.ratio))
    .map(item => ({
      id: item.id,
      ratio: item.latest.ratio,
      naturalY: (1 - item.latest.ratio / maxRatio) * plotHeight,
    }))
    .sort((left, right) => left.naturalY - right.naturalY)
  if (!labels.length) return []

  const gap = labels.length > 1
    ? Math.min(minGap, plotHeight / (labels.length - 1))
    : 0
  labels[0].y = Math.max(0, labels[0].naturalY)
  for (let index = 1; index < labels.length; index += 1) {
    labels[index].y = Math.max(labels[index].naturalY, labels[index - 1].y + gap)
  }
  if (labels.at(-1).y > plotHeight) {
    labels[labels.length - 1].y = plotHeight
    for (let index = labels.length - 2; index >= 0; index -= 1) {
      labels[index].y = Math.min(labels[index].y, labels[index + 1].y - gap)
    }
  }
  if (labels[0].y < 0) {
    const shift = -labels[0].y
    labels.forEach(label => { label.y += shift })
  }
  return labels
}
