import test from 'node:test'
import assert from 'node:assert/strict'

import {
  chartDomain,
  formatRatio,
  formatUsd,
  selectMemorySeries,
} from '../src/utils/memoryLeverage.mjs'


const series = [
  { id: 'sandisk_all', company_id: 'sandisk', scope: 'all', points: [] },
  { id: 'sk_hynix_all', company_id: 'sk_hynix', scope: 'all', points: [] },
  { id: 'sk_hynix_kr', company_id: 'sk_hynix', scope: 'kr', points: [] },
  { id: 'samsung_all', company_id: 'samsung', scope: 'all', points: [] },
  { id: 'samsung_kr', company_id: 'samsung', scope: 'kr', points: [] },
  { id: 'kioxia_all', company_id: 'kioxia', scope: 'all', points: [] },
]


test('global scope hides duplicate KR-only series', () => {
  assert.deepEqual(
    selectMemorySeries(series, 'all').map(item => item.id),
    ['sandisk_all', 'sk_hynix_all', 'samsung_all', 'kioxia_all'],
  )
})


test('KR scope swaps only Korean companies to their KR legs', () => {
  assert.deepEqual(
    selectMemorySeries(series, 'kr').map(item => item.id),
    ['sandisk_all', 'sk_hynix_kr', 'samsung_kr', 'kioxia_all'],
  )
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
