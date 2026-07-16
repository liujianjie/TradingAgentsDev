import test from 'node:test'
import assert from 'node:assert/strict'

import {
  chartDomain,
  chartInteractionDates,
  chartLinePattern,
  chartMonthTicks,
  chartSnapshotAtX,
  chartYAxisTicks,
  displayCompanyName,
  filterSeriesByDays,
  formatPercent,
  formatRatio,
  formatUsd,
  leverageMetrics,
  leverageProductCount,
  layoutEndLabels,
  selectSnapshotDates,
  selectSeriesSnapshot,
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


test('company cards remove duplicated English scope suffixes', () => {
  assert.equal(displayCompanyName('SK hynix (all)'), 'SK hynix')
  assert.equal(displayCompanyName('Samsung (KR)'), 'Samsung')
  assert.equal(displayCompanyName('Micron'), 'Micron')
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
  assert.equal(formatPercent(0.8123), '81.2%')
  assert.equal(formatPercent(null), '—')
  assert.equal(formatUsd(1_591_000_000), '$1.59B')
  assert.equal(formatUsd(243_000_000), '$243M')
})


test('latest leverage metrics expose total turnover and long-short composition', () => {
  const metrics = leverageMetrics({
    long_turnover_usd: 20,
    short_turnover_usd: 10,
    underlying_turnover_usd: 100,
  })

  assert.equal(metrics.totalTurnoverUsd, 30)
  assert.equal(metrics.longShare, 2 / 3)
  assert.equal(metrics.shortShare, 1 / 3)
})


test('product count follows the selected global or Korea-only scope', () => {
  const coverage = [
    { company_id: 'sk_hynix', role: 'leveraged', venue: 'KRX', status: 'ok' },
    { company_id: 'sk_hynix', role: 'leveraged', venue: 'HKEX', status: 'ok' },
    { company_id: 'sk_hynix', role: 'leveraged', venue: 'NYSE', status: 'missing' },
    { company_id: 'sk_hynix', role: 'underlying', venue: 'KRX', status: 'ok' },
    { company_id: 'samsung', role: 'leveraged', venue: 'KRX', status: 'ok' },
  ]

  assert.equal(
    leverageProductCount(coverage, { company_id: 'sk_hynix', scope: 'all' }),
    2,
  )
  assert.equal(
    leverageProductCount(coverage, { company_id: 'sk_hynix', scope: 'kr' }),
    1,
  )
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


test('history window is filtered locally without changing the latest reading', () => {
  const source = [{
    id: 'micron_all',
    latest: { date: '2026-07-15', ratio: 0.3 },
    points: [
      { date: '2026-06-01', ratio: 0.1 },
      { date: '2026-07-01', ratio: 0.2 },
      { date: '2026-07-15', ratio: 0.3 },
    ],
  }]

  const filtered = filterSeriesByDays(source, 30, '2026-07-15')

  assert.deepEqual(filtered[0].points.map(point => point.date), ['2026-07-01', '2026-07-15'])
  assert.equal(filtered[0].latest.ratio, 0.3)
  assert.equal(source[0].points.length, 3)
})


test('snapshot dates use common trading dates and support previous sessions', () => {
  const source = [
    {
      points: [
        { date: '2026-07-11', ratio: 0.1 },
        { date: '2026-07-14', ratio: 0.2 },
        { date: '2026-07-15', ratio: 0.3 },
      ],
    },
    {
      points: [
        { date: '2026-07-10', ratio: 0.4 },
        { date: '2026-07-14', ratio: 0.5 },
        { date: '2026-07-15', ratio: 0.6 },
      ],
    },
  ]

  assert.deepEqual(selectSnapshotDates(source, 5), ['2026-07-15', '2026-07-14'])
})


test('selected snapshot replaces card latest metrics with the chosen day', () => {
  const source = [{
    id: 'sandisk_all',
    latest: { date: '2026-07-15', ratio: 0.3 },
    points: [
      {
        date: '2026-07-14',
        ratio: 0.2,
        change_1d: 0.05,
        long_turnover_usd: 20,
        short_turnover_usd: 5,
        leverage_weighted_ratio: 0.4,
        underlying_turnover_usd: 125,
      },
      { date: '2026-07-15', ratio: 0.3 },
    ],
  }]

  const selected = selectSeriesSnapshot(source, '2026-07-14')

  assert.equal(selected[0].latest.date, '2026-07-14')
  assert.equal(selected[0].latest.long_turnover_usd, 20)
  assert.equal(source[0].latest.date, '2026-07-15')
})


test('chart interaction snaps to the nearest real trading date', () => {
  const source = [
    {
      id: 'micron_all',
      company_name: 'Micron',
      scope: 'all',
      color: '#123456',
      points: [
        { date: '2026-07-10', ratio: 0.10 },
        { date: '2026-07-14', ratio: 0.20 },
      ],
    },
    {
      id: 'samsung_kr',
      company_name: 'Samsung (KR)',
      scope: 'kr',
      color: '#654321',
      points: [{ date: '2026-07-14', ratio: 0.40 }],
    },
  ]

  const snapshot = chartSnapshotAtX(
    source,
    76,
    { plotLeft: 10, plotRight: 110, minTime: Date.parse('2026-07-10'), maxTime: Date.parse('2026-07-14') },
  )

  assert.equal(snapshot.date, '2026-07-14')
  assert.equal(snapshot.rows[0].ratio, 0.20)
  assert.equal(snapshot.rows[1].ratio, 0.40)
})


test('chart interaction clamps outside positions and keeps missing series explicit', () => {
  const source = [
    {
      id: 'sandisk_all',
      company_name: 'SanDisk',
      scope: 'all',
      color: '#123456',
      points: [
        { date: '2026-07-10', ratio: 0.10 },
        { date: '2026-07-14', ratio: 0.20 },
      ],
    },
    {
      id: 'kioxia_all',
      company_name: 'Kioxia',
      scope: 'all',
      color: '#654321',
      points: [{ date: '2026-07-14', ratio: 0 }],
    },
    {
      id: 'micron_all',
      company_name: 'Micron',
      scope: 'all',
      color: '#abcdef',
      points: [{ date: '2026-07-14', ratio: null }],
    },
  ]

  const earliest = chartSnapshotAtX(
    source,
    -100,
    { plotLeft: 10, plotRight: 110, minTime: Date.parse('2026-07-10'), maxTime: Date.parse('2026-07-14') },
  )
  const latest = chartSnapshotAtX(
    source,
    999,
    { plotLeft: 10, plotRight: 110, minTime: Date.parse('2026-07-10'), maxTime: Date.parse('2026-07-14') },
  )

  assert.deepEqual(chartInteractionDates(source), ['2026-07-10', '2026-07-14'])
  assert.equal(earliest.date, '2026-07-10')
  assert.equal(earliest.rows[1].ratio, null)
  assert.equal(latest.date, '2026-07-14')
  assert.equal(latest.rows[1].ratio, 0)
  assert.equal(latest.rows[2].ratio, null)
})
