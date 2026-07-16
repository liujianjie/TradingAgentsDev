<template>
  <view class="card metric-card">
    <view class="metric-top">
      <view class="company-line">
        <view class="company-dot" :style="{ backgroundColor: item.color }" />
        <text class="company-name">{{ item.company_name }}</text>
      </view>
      <text class="market-badge">{{ item.scope === 'kr' ? '仅韩国' : '全球' }}</text>
    </view>

    <template v-if="item.latest">
      <text class="primary-label">杠杆成交比</text>
      <view class="metric-main">
        <text class="ratio-value">{{ formatRatio(item.latest.ratio) }}</text>
        <text :class="['ratio-change', changeClass(item.latest.change_1d)]">
          {{ formatChange(item.latest.change_1d) }}
        </text>
      </view>
      <text class="ratio-reading">
        每 $1 正股成交，对应 ${{ formatRatio(item.latest.ratio) }} 杠杆产品成交
      </text>

      <view class="turnover-summary">
        <view class="summary-item">
          <text class="summary-label">杠杆产品合计成交额</text>
          <text class="summary-value">{{ formatUsd(metrics.totalTurnoverUsd) }}</text>
        </view>
        <view class="summary-item">
          <text class="summary-label">正股 / ADR / GDR 成交额</text>
          <text class="summary-value">{{ formatUsd(item.latest.underlying_turnover_usd) }}</text>
        </view>
      </view>

      <view class="mix-section">
        <view class="mix-head">
          <text class="mix-title">杠杆产品内部构成</text>
          <text class="mix-caption">按实际成交额</text>
        </view>
        <view class="mix-bar" aria-label="正向和反向杠杆产品成交额占比">
          <view
            class="mix-long"
            :style="{ width: `${(metrics.longShare || 0) * 100}%` }"
          />
          <view
            class="mix-short"
            :style="{ width: `${(metrics.shortShare || 0) * 100}%` }"
          />
        </view>
        <view class="mix-legend">
          <text>正向 {{ formatPercent(metrics.longShare) }}</text>
          <text>反向 {{ formatPercent(metrics.shortShare) }}</text>
        </view>
      </view>

      <view class="metric-details">
        <view class="detail-item">
          <text class="detail-label">正向杠杆成交额</text>
          <text class="detail-value">{{ formatUsd(item.latest.long_turnover_usd) }}</text>
        </view>
        <view class="detail-item">
          <text class="detail-label">反向杠杆成交额</text>
          <text class="detail-value">{{ formatUsd(item.latest.short_turnover_usd) }}</text>
        </view>
        <view class="detail-item detail-highlight">
          <text class="detail-label">杠杆倍数折算比</text>
          <text class="detail-value">{{ formatRatio(item.latest.leverage_weighted_ratio) }}</text>
          <text class="detail-hint">2倍产品按2倍折算</text>
        </view>
        <view class="detail-item">
          <text class="detail-label">纳入杠杆产品</text>
          <text class="detail-value">{{ productCount }} 只</text>
          <text class="detail-hint">有当日有效行情</text>
        </view>
      </view>
    </template>

    <text v-else class="ratio-empty">暂无有效读数</text>
  </view>
</template>

<script setup>
import { computed } from 'vue'
import {
  formatPercent,
  formatRatio,
  formatUsd,
  leverageMetrics,
} from '@/utils/memoryLeverage.mjs'

const props = defineProps({
  item: { type: Object, required: true },
  productCount: { type: Number, default: 0 },
})

const metrics = computed(() => leverageMetrics(props.item.latest))

function formatChange(value) {
  if (!Number.isFinite(value)) return '较前日 —'
  const sign = value > 0 ? '+' : ''
  return `较前日 ${sign}${value.toFixed(3)}`
}

function changeClass(value) {
  if (!Number.isFinite(value) || value === 0) return 'change-flat'
  return value > 0 ? 'change-up' : 'change-down'
}
</script>

<style lang="scss" scoped>
.metric-card { padding: 28rpx; }
.metric-top, .company-line, .metric-main, .mix-head, .mix-legend {
  display: flex;
  align-items: center;
}
.metric-top, .mix-head, .mix-legend { justify-content: space-between; }
.company-dot { width: 16rpx; height: 16rpx; flex: none; border-radius: 50%; }
.company-name { margin-left: 12rpx; color: $text; font-size: 27rpx; font-weight: 700; }
.market-badge {
  padding: 6rpx 14rpx;
  border-radius: $radius-pill;
  background: $surface-2;
  color: $text-3;
  font-size: 20rpx;
  font-weight: 700;
}
.primary-label { display: block; margin-top: 22rpx; color: $text-3; font-size: 20rpx; }
.metric-main { margin-top: 2rpx; align-items: baseline; gap: 18rpx; }
.ratio-value { color: $text; font-size: 54rpx; font-weight: 800; font-variant-numeric: tabular-nums; }
.ratio-change { font-size: 21rpx; font-weight: 700; }
.change-up { color: $sell; }
.change-down { color: $buy; }
.change-flat { color: $text-3; }
.ratio-reading {
  display: block;
  margin-top: 2rpx;
  color: $text-2;
  font-size: 21rpx;
  line-height: 1.5;
}
.turnover-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12rpx;
  margin-top: 24rpx;
}
.summary-item { min-width: 0; padding: 20rpx; border-radius: $radius-sm; background: $surface-2; }
.summary-label, .summary-value { display: block; }
.summary-label { min-height: 58rpx; color: $text-3; font-size: 19rpx; line-height: 1.45; }
.summary-value { margin-top: 8rpx; color: $text; font-size: 29rpx; font-weight: 800; font-variant-numeric: tabular-nums; }
.mix-section { margin-top: 24rpx; }
.mix-title { color: $text-2; font-size: 21rpx; font-weight: 700; }
.mix-caption, .mix-legend { color: $text-3; font-size: 18rpx; }
.mix-bar { display: flex; height: 12rpx; overflow: hidden; margin-top: 13rpx; border-radius: $radius-pill; background: $surface-2; }
.mix-long { background: #4f6ef7; }
.mix-short { background: #e09b43; }
.mix-legend { margin-top: 9rpx; }
.metric-details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18rpx 24rpx;
  margin-top: 22rpx;
  padding-top: 22rpx;
  border-top: 1rpx solid $line;
}
.detail-label, .detail-value, .detail-hint { display: block; }
.detail-label { color: $text-3; font-size: 20rpx; }
.detail-value { margin-top: 5rpx; color: $text-2; font-size: 24rpx; font-weight: 700; font-variant-numeric: tabular-nums; }
.detail-hint { margin-top: 4rpx; color: $text-3; font-size: 17rpx; line-height: 1.4; }
.detail-highlight .detail-value { color: $primary; }
.ratio-empty { display: block; margin-top: 24rpx; color: $text-3; }

@media (max-width: 360px) {
  .turnover-summary, .metric-details { grid-template-columns: 1fr; }
  .summary-label { min-height: 0; }
}
</style>
