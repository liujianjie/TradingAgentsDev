<template>
  <view class="chart-shell">
    <view class="chart-header">
      <view>
        <text class="chart-kicker">MEMORY SECTOR · TURNOVER LEVERAGE</text>
        <text class="chart-title">存储板块杠杆率</text>
      </view>
      <view class="as-of-block">
        <text class="as-of-label">THROUGH</text>
        <text class="as-of-value">{{ asOf || '—' }}</text>
      </view>
    </view>

    <view class="line-key" aria-label="线型说明">
      <view class="key-item">
        <view class="key-stroke key-solid" />
        <text>全部市场</text>
      </view>
      <view class="key-item">
        <view class="key-stroke key-dashed" />
        <text>仅韩国上市产品</text>
      </view>
      <view class="key-item">
        <view class="key-stroke key-dotted" />
        <text>暂无杠杆产品</text>
      </view>
    </view>

    <canvas
      v-if="domain"
      id="memoryRatioChart"
      canvas-id="memoryRatioChart"
      class="chart-canvas"
      aria-label="存储板块杠杆率历史趋势图，右侧标注各序列最新值"
    />
    <view v-else class="chart-empty" role="status">
      <text>当前窗口没有可绘制的数据</text>
    </view>

    <view class="chart-foot">
      <text>RATIO = 杠杆 ETF / ETN / ETP 美元成交额 ÷ 对应正股美元成交额</text>
      <text class="chart-foot-note">右侧数字为最新完整交易日读数</text>
    </view>

    <view class="sr-only" aria-label="图表最新数值">
      <text v-for="item in series" :key="item.id">
        {{ item.company_name }} {{ formatRatio(item.latest?.ratio) }}；
      </text>
    </view>
  </view>
</template>

<script setup>
import { computed, getCurrentInstance, nextTick, onMounted, watch } from 'vue'
import {
  chartDomain,
  chartLinePattern,
  chartMonthTicks,
  chartYAxisTicks,
  formatRatio,
  layoutEndLabels,
} from '@/utils/memoryLeverage.mjs'

const props = defineProps({
  series: { type: Array, default: () => [] },
  asOf: { type: String, default: '' },
})

const component = getCurrentInstance()
const domain = computed(() => chartDomain(props.series))

function setDash(ctx, pattern) {
  if (typeof ctx.setLineDash === 'function') ctx.setLineDash(pattern, 0)
}

function validPoints(item) {
  return (item.points || [])
    .map(point => ({ time: Date.parse(point.date), ratio: Number(point.ratio) }))
    .filter(point => Number.isFinite(point.time) && Number.isFinite(point.ratio))
}

function drawChart() {
  if (!domain.value) return
  const query = uni.createSelectorQuery().in(component?.proxy)
  query.select('#memoryRatioChart').boundingClientRect(rect => {
    if (!rect?.width || !rect?.height) return
    const ctx = uni.createCanvasContext('memoryRatioChart', component?.proxy)
    const width = rect.width
    const height = rect.height
    const compact = width < 520
    const pad = {
      left: compact ? 34 : 46,
      right: compact ? 118 : width < 760 ? 164 : 206,
      top: 18,
      bottom: 34,
    }
    const plotWidth = width - pad.left - pad.right
    const plotHeight = height - pad.top - pad.bottom
    const { minTime, maxTime, maxRatio } = domain.value
    const timeSpan = Math.max(maxTime - minTime, 24 * 60 * 60 * 1000)
    const plotRight = pad.left + plotWidth
    const axisColor = '#7b8178'
    const gridColor = '#30342f'
    const background = '#171916'
    const yTicks = chartYAxisTicks(maxRatio)

    ctx.clearRect(0, 0, width, height)
    ctx.setFillStyle(background)
    ctx.fillRect(0, 0, width, height)
    setDash(ctx, [])
    ctx.setFontSize(compact ? 9 : 11)
    ctx.setTextAlign('right')
    ctx.setTextBaseline('middle')

    for (const value of yTicks) {
      const y = pad.top + (1 - value / maxRatio) * plotHeight
      ctx.beginPath()
      ctx.setStrokeStyle(gridColor)
      ctx.setLineWidth(1)
      ctx.moveTo(pad.left, y)
      ctx.lineTo(plotRight, y)
      ctx.stroke()
      ctx.setFillStyle(axisColor)
      ctx.fillText(value < 10 ? value.toFixed(1) : value.toLocaleString('en-US'), pad.left - 7, y)
    }

    const monthTicks = chartMonthTicks(props.series, compact ? 4 : 7)
    ctx.setTextBaseline('top')
    monthTicks.forEach((tick, index) => {
      const x = pad.left + ((tick.time - minTime) / timeSpan) * plotWidth
      ctx.setTextAlign(index === 0 ? 'left' : 'center')
      ctx.setFillStyle(axisColor)
      ctx.fillText(tick.label, x, height - pad.bottom + 11)
    })

    for (const item of props.series) {
      const points = validPoints(item)
      if (!points.length) continue
      ctx.beginPath()
      ctx.setStrokeStyle(item.color)
      ctx.setLineWidth(item.scope === 'kr' ? 1.7 : item.company_id === 'kioxia' ? 1.2 : 2.2)
      setDash(ctx, chartLinePattern(item))
      points.forEach((point, index) => {
        const x = pad.left + ((point.time - minTime) / timeSpan) * plotWidth
        const y = pad.top + (1 - point.ratio / maxRatio) * plotHeight
        if (index === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.stroke()
    }

    const labelLayouts = new Map(
      layoutEndLabels(props.series, maxRatio, plotHeight, compact ? 13 : 17)
        .map(label => [label.id, label]),
    )
    setDash(ctx, [])
    ctx.setTextAlign('left')
    ctx.setTextBaseline('middle')
    ctx.setFontSize(compact ? 8 : 11)
    for (const item of props.series) {
      const points = validPoints(item)
      const latestPoint = points.at(-1)
      const label = labelLayouts.get(item.id)
      if (!latestPoint || !label) continue
      const pointY = pad.top + (1 - latestPoint.ratio / maxRatio) * plotHeight
      const labelY = pad.top + label.y
      const labelX = plotRight + (compact ? 11 : 17)

      ctx.beginPath()
      ctx.setStrokeStyle(item.color)
      ctx.setLineWidth(1)
      ctx.moveTo(plotRight + 2, pointY)
      ctx.lineTo(labelX - 4, labelY)
      ctx.stroke()

      ctx.beginPath()
      ctx.setFillStyle(item.color)
      ctx.arc(plotRight + 2, pointY, compact ? 1.8 : 2.4, 0, Math.PI * 2)
      ctx.fill()

      ctx.setFillStyle(item.color)
      ctx.fillText(`${item.company_name}  ${formatRatio(item.latest?.ratio)}`, labelX, labelY)
    }

    setDash(ctx, [])
    ctx.draw()
  }).exec()
}

watch(
  () => [props.series, props.asOf],
  () => nextTick(drawChart),
  { deep: true },
)
onMounted(() => nextTick(drawChart))
</script>

<style lang="scss" scoped>
.chart-shell {
  position: relative;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
  padding: 30rpx 28rpx 22rpx;
  border: 1rpx solid #30342f;
  border-radius: 14rpx;
  background:
    radial-gradient(circle at 85% 0%, rgba(217, 144, 0, .08), transparent 28%),
    #171916;
  color: #f2f3ef;
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, .035), 0 14rpx 34rpx rgba(18, 21, 18, .18);
  font-family: Bahnschrift, "DIN Alternate", "Cascadia Code", "Microsoft YaHei", sans-serif;
}
.chart-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24rpx; }
.chart-kicker {
  display: block;
  color: #8c9489;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 18rpx;
  font-weight: 650;
  letter-spacing: 2.4rpx;
}
.chart-title { display: block; margin-top: 8rpx; color: #f4f5f1; font-size: 34rpx; font-weight: 800; letter-spacing: .6rpx; }
.as-of-block { flex: none; padding-top: 2rpx; text-align: right; }
.as-of-label { display: block; color: #747b71; font-family: "Cascadia Code", monospace; font-size: 16rpx; letter-spacing: 2rpx; }
.as-of-value { display: block; margin-top: 7rpx; color: #d99000; font-family: "Cascadia Code", monospace; font-size: 21rpx; font-weight: 700; }
.line-key { display: flex; flex-wrap: wrap; gap: 12rpx 26rpx; margin-top: 22rpx; color: #929990; font-size: 18rpx; }
.key-item { display: flex; align-items: center; gap: 10rpx; }
.key-stroke { width: 38rpx; height: 0; border-top: 3rpx solid #b8bdb5; }
.key-dashed { border-top-style: dashed; }
.key-dotted { border-top-style: dotted; }
.chart-canvas { width: 100%; height: 690rpx; margin-top: 12rpx; }
.chart-empty {
  height: 420rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 24rpx;
  color: #8c9489;
  border: 1rpx dashed #343933;
  background: rgba(255,255,255,.015);
}
.chart-foot {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid #2b2f2a;
  color: #727970;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 16rpx;
  line-height: 1.55;
}
.chart-foot-note { flex: none; color: #8f968c; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

@media (min-width: 768px) {
  .chart-shell { padding: 28px 30px 20px; }
  .chart-title { font-size: 25px; }
  .chart-kicker { font-size: 11px; }
  .as-of-label { font-size: 10px; }
  .as-of-value { font-size: 13px; }
  .line-key { margin-top: 16px; font-size: 11px; }
  .chart-canvas { height: 560px; margin-top: 6px; }
  .chart-foot { padding-top: 12px; font-size: 10px; }
}

@media (max-width: 420px) {
  .chart-shell { padding-left: 20rpx; padding-right: 20rpx; }
  .chart-title { font-size: 31rpx; }
  .chart-kicker { font-size: 15rpx; letter-spacing: 1.4rpx; }
  .as-of-value { font-size: 18rpx; }
  .line-key { gap: 10rpx 18rpx; font-size: 16rpx; }
  .key-stroke { width: 30rpx; }
  .chart-foot { flex-direction: column; }
  .chart-foot-note { flex: auto; }
}
</style>
