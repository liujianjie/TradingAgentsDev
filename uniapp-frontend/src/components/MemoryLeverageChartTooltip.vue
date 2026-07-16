<template>
  <view
    v-if="snapshot"
    :class="['chart-tooltip', align === 'left' ? 'tooltip-left' : 'tooltip-right']"
    role="status"
    aria-live="polite"
  >
    <view class="tooltip-head">
      <text class="tooltip-label">交易日</text>
      <text class="tooltip-date">{{ snapshot.date }}</text>
    </view>
    <view class="tooltip-list">
      <view v-for="row in snapshot.rows" :key="row.id" class="tooltip-row">
        <view class="tooltip-name-line">
          <view class="tooltip-dot" :style="{ backgroundColor: row.color }" />
          <text class="tooltip-name">{{ displayCompanyName(row.companyName) }}</text>
          <text class="tooltip-scope">{{ row.scope === 'kr' ? '韩国' : '全球' }}</text>
        </view>
        <text class="tooltip-ratio">{{ formatRatio(row.ratio) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { displayCompanyName, formatRatio } from '@/utils/memoryLeverage.mjs'

defineProps({
  snapshot: { type: Object, default: null },
  align: { type: String, default: 'right' },
})
</script>

<style lang="scss" scoped>
.chart-tooltip {
  position: absolute;
  z-index: 3;
  top: 18rpx;
  width: 180px;
  box-sizing: border-box;
  padding: 18rpx 20rpx;
  border: 1rpx solid rgba(217, 144, 0, .48);
  border-radius: 10rpx;
  background: rgba(20, 22, 19, .94);
  box-shadow: 0 12rpx 30rpx rgba(0, 0, 0, .3);
  pointer-events: none;
  backdrop-filter: blur(8px);
}
.tooltip-left { left: 34px; }
.tooltip-right { right: 118px; }
.tooltip-head { display: flex; align-items: baseline; justify-content: space-between; gap: 14rpx; padding-bottom: 12rpx; border-bottom: 1rpx solid #343933; }
.tooltip-label { color: #7f877c; font-size: 17rpx; }
.tooltip-date { color: #f0b33e; font-family: "Cascadia Code", Consolas, monospace; font-size: 20rpx; font-weight: 800; }
.tooltip-list { margin-top: 8rpx; }
.tooltip-row { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; min-height: 37rpx; }
.tooltip-name-line { display: flex; min-width: 0; align-items: center; gap: 8rpx; }
.tooltip-dot { width: 10rpx; height: 10rpx; flex: none; border-radius: 50%; }
.tooltip-name { overflow: hidden; color: #c4c9c1; font-size: 18rpx; text-overflow: ellipsis; white-space: nowrap; }
.tooltip-scope { flex: none; color: #6f776c; font-size: 14rpx; }
.tooltip-ratio { flex: none; color: #f2f3ef; font-family: "Cascadia Code", Consolas, monospace; font-size: 19rpx; font-weight: 800; font-variant-numeric: tabular-nums; }

@media (min-width: 768px) {
  .chart-tooltip { top: 14px; width: 220px; padding: 12px 14px; border-radius: 7px; }
  .tooltip-left { left: 46px; }
  .tooltip-right { right: 206px; }
  .tooltip-head { gap: 10px; padding-bottom: 8px; }
  .tooltip-label { font-size: 10px; }
  .tooltip-date { font-size: 12px; }
  .tooltip-list { margin-top: 5px; }
  .tooltip-row { min-height: 24px; gap: 8px; }
  .tooltip-name-line { gap: 6px; }
  .tooltip-dot { width: 6px; height: 6px; }
  .tooltip-name { font-size: 11px; }
  .tooltip-scope { font-size: 9px; }
  .tooltip-ratio { font-size: 12px; }
}

@media (max-width: 350px) {
  .chart-tooltip { width: 164px; }
  .tooltip-right { right: 104px; }
}
</style>
