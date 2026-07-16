<template>
  <view class="chart-shell">
    <canvas
      v-if="domain"
      id="memoryRatioChart"
      canvas-id="memoryRatioChart"
      class="chart-canvas"
      aria-label="存储板块杠杆率历史趋势图"
    />
    <view v-else class="chart-empty" role="status">
      <text>当前窗口没有可绘制的数据</text>
    </view>

    <view class="legend" aria-label="图例和最新数值">
      <view v-for="item in series" :key="item.id" class="legend-item">
        <view class="legend-dot" :style="{ backgroundColor: item.color }" />
        <text class="legend-name">{{ item.company_name }}</text>
        <text class="legend-value">{{ formatRatio(item.latest?.ratio) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, getCurrentInstance, nextTick, onMounted, watch } from 'vue'
import { chartDomain, formatRatio } from '@/utils/memoryLeverage.mjs'

const props = defineProps({
  series: { type: Array, default: () => [] },
})

const component = getCurrentInstance()
const domain = computed(() => chartDomain(props.series))

function drawChart() {
  if (!domain.value) return
  const query = uni.createSelectorQuery().in(component?.proxy)
  query.select('#memoryRatioChart').boundingClientRect(rect => {
    if (!rect?.width || !rect?.height) return
    const ctx = uni.createCanvasContext('memoryRatioChart', component?.proxy)
    const width = rect.width
    const height = rect.height
    const pad = { left: 38, right: 14, top: 14, bottom: 30 }
    const plotWidth = width - pad.left - pad.right
    const plotHeight = height - pad.top - pad.bottom
    const { minTime, maxTime, maxRatio } = domain.value
    const timeSpan = Math.max(maxTime - minTime, 24 * 60 * 60 * 1000)

    ctx.clearRect(0, 0, width, height)
    ctx.setFontSize(10)
    ctx.setTextAlign('right')
    ctx.setTextBaseline('middle')
    for (let step = 0; step <= 4; step += 1) {
      const y = pad.top + plotHeight * (step / 4)
      const value = maxRatio * (1 - step / 4)
      ctx.beginPath()
      ctx.setStrokeStyle('#e8ebf2')
      ctx.setLineWidth(1)
      ctx.moveTo(pad.left, y)
      ctx.lineTo(width - pad.right, y)
      ctx.stroke()
      ctx.setFillStyle('#8d94a7')
      ctx.fillText(value.toFixed(1), pad.left - 6, y)
    }

    for (const item of props.series) {
      const points = (item.points || [])
        .map(point => ({ time: Date.parse(point.date), ratio: Number(point.ratio) }))
        .filter(point => Number.isFinite(point.time) && Number.isFinite(point.ratio))
      if (!points.length) continue
      ctx.beginPath()
      ctx.setStrokeStyle(item.color)
      ctx.setLineWidth(2)
      points.forEach((point, index) => {
        const x = pad.left + ((point.time - minTime) / timeSpan) * plotWidth
        const y = pad.top + (1 - point.ratio / maxRatio) * plotHeight
        if (index === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.stroke()
    }

    ctx.setFillStyle('#8d94a7')
    ctx.setFontSize(10)
    ctx.setTextBaseline('bottom')
    ctx.setTextAlign('left')
    ctx.fillText(new Date(minTime).toISOString().slice(5, 10), pad.left, height - 4)
    ctx.setTextAlign('right')
    ctx.fillText(new Date(maxTime).toISOString().slice(5, 10), width - pad.right, height - 4)
    ctx.draw()
  }).exec()
}

watch(
  () => props.series,
  () => nextTick(drawChart),
  { deep: true },
)
onMounted(() => nextTick(drawChart))
</script>

<style lang="scss" scoped>
.chart-shell { width: 100%; }
.chart-canvas { width: 100%; height: 500rpx; }
.chart-empty {
  height: 360rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $text-3;
  background: $surface-2;
  border-radius: $radius-sm;
}
.legend {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14rpx 24rpx;
  margin-top: 20rpx;
}
.legend-item { display: flex; align-items: center; min-width: 0; }
.legend-dot { width: 14rpx; height: 14rpx; border-radius: 50%; flex: none; }
.legend-name {
  margin-left: 10rpx;
  color: $text-2;
  font-size: 23rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.legend-value { margin-left: auto; padding-left: 10rpx; color: $text; font-weight: 700; }

@media (min-width: 768px) {
  .chart-canvas { height: 420px; }
  .legend { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
