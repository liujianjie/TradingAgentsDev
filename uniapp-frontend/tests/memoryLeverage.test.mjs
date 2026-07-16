import test from 'node:test'
import assert from 'node:assert/strict'

import {
  chartDomain,
  chartLinePattern,
  chartMonthTicks,
  chartYAxisTicks,
  formatRatio,
  formatUsd,
  layoutEndLabels,
  selectChartSeries,
  selectMemorySeries,
} from '../src/utils/memoryLeverage.mjs'


const series = [
  { id: 'sandisk_all', company_id: 'sandisk', scope: 'all', points: [] },
  { id: 'micron_all', company_id: 'micron', scope: 'all', points: [] },
  { id: 'sk_hynix_all', company_id: 'sk_hynix', scope: 'all', points: [] },
  { id: 'sk_hynix_kr', company_id: 'sk_hynix', scope: 'kr', points: [] },
  { id: 'samsung_all', company_id: 'samsung', scope: 'all', points: [] },
  { id: 'samsung_kr', company_id: 'samsung', scope: 'kr', points: [] },
  { id: 'kioxia_all', company_id: 'kioxia', scope: 'all', points: [] },
]


test('global scope hides duplicate KR-only series', () => {
  assert.deepEqual(
    selectMemorySeries(series, 'all').map(item => item.id),
    ['sandisk_all', 'micron_all', 'sk_hynix_all', 'samsung_all', 'kioxia_all'],
  )
})


test('KR scope swaps only Korean companies to their KR legs', () => {
  assert.deepEqual(
    selectMemorySeries(series, 'kr').map(item => item.id),
    ['sandisk_all', 'micron_all', 'sk_hynix_kr', 'samsung_kr', 'kioxia_all'],
  )
})


test('chart keeps global and KR legs together in the reference reading order', () => {
  assert.deepEqual(
    selectChartSeries([...series].reverse()).map(item => item.id),
    [
      'sandisk_all',
      'micron_all',
      'sk_hynix_all',
      'sk_hynix_kr',
      'samsung_all',
      'samsung_kr',
      'kioxia_all',
    ],
  )
})


test('chart exposes solid, dashed and dotted comparison semantics', () => {
  assert.deepEqual(chartLinePattern({ company_id: 'sandisk', scope: 'all' }), [])
  assert.deepEqual(chartLinePattern({ company_id: 'sk_hynix', scope: 'kr' }), [7, 5])
  assert.deepEqual(chartLinePattern({ company_id: 'kioxia', scope: 'all' }), [2, 4])
})


test('chart builds readable month ticks across the visible history', () => {
  const ticks = chartMonthTicks([
    {
      points: [
        { date: '2026-01-15', ratio: 0.1 },
        { date: '2026-02-08', ratio: 0.2 },
        { date: '2026-03-09', ratio: 0.3 },
      ],
    },
  ])

  assert.deepEqual(ticks.map(item => item.label), ['1月', '2月', '3月'])
})


test('y axis always uses a bounded number of readable ticks', () => {
  const normal = chartYAxisTicks(1.4)
  const polluted = chartYAxisTicks(21_767)

  assert.ok(normal.length >= 4 && normal.length <= 8)
  assert.ok(polluted.length >= 4 && polluted.length <= 8)
  assert.equal(normal[0], 0)
  assert.equal(normal.at(-1), 1.4)
  assert.equal(polluted.at(-1), 21_767)
})


test('direct end labels are separated when latest values cluster', () => {
  const labels = layoutEndLabels(
    [
      { id: 'a', latest: { ratio: 0.40 } },
      { id: 'b', latest: { ratio: 0.39 } },
      { id: 'c', latest: { ratio: 0.38 } },
    ],
    0.5,
    100,
    16,
  )

  assert.equal(labels.length, 3)
  assert.ok(labels[1].y - labels[0].y >= 16)
  assert.ok(labels[2].y - labels[1].y >= 16)
})


test('formatters keep ratios and large dollar turnover scannable', () => {
  assert.equal(formatRatio(0.10384), '0.104')
  assert.equal(formatRatio(null), '—')
  assert.equal(formatUsd(1_591_000_000), '$1.59B')
  assert.equal(formatUsd(243_000_000), '$243M')
})


test('chart domain ignores invalid points and keeps a non-zero y range', () => {
  const domain = chartDomain([
    {
      points: [
        { date: '2026-07-09', ratio: 0 },
        { date: '2026-07-10', ratio: 0.37 },
        { date: 'bad', ratio: Number.NaN },
      ],
    },
  ])

  assert.equal(domain.minTime, Date.parse('2026-07-09'))
  assert.equal(domain.maxTime, Date.parse('2026-07-10'))
  assert.equal(domain.maxRatio, 0.4)
})
