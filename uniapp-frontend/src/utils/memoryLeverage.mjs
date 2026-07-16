const KOREAN_COMPANIES = new Set(['sk_hynix', 'samsung'])


export function selectMemorySeries(series, scope) {
  if (!Array.isArray(series)) return []
  if (scope !== 'kr') return series.filter(item => item.scope === 'all')
  return series.filter(item => {
    if (KOREAN_COMPANIES.has(item.company_id)) return item.scope === 'kr'
    return item.scope === 'all'
  })
}


export function formatRatio(value) {
  return Number.isFinite(value) ? value.toFixed(3) : '—'
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


export function chartDomain(series) {
  const points = (series || [])
    .flatMap(item => item.points || [])
    .map(point => ({ time: Date.parse(point.date), ratio: Number(point.ratio) }))
    .filter(point => Number.isFinite(point.time) && Number.isFinite(point.ratio) && point.ratio >= 0)
  if (!points.length) return null
  const times = points.map(point => point.time)
  const ratios = points.map(point => point.ratio)
  const rawMax = Math.max(...ratios)
  return {
    minTime: Math.min(...times),
    maxTime: Math.max(...times),
    maxRatio: Math.max(0.1, Math.ceil(rawMax * 10) / 10),
  }
}
