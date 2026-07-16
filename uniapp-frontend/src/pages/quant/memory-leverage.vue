<template>
  <view class="page">
    <view class="grad-header hero">
      <view class="hero-topline">
        <text class="eyebrow">量化工具箱</text>
        <button class="hero-refresh" :disabled="loading" @click="load(true)">
          {{ loading ? '更新中' : '刷新数据' }}
        </button>
      </view>
      <text class="title">存储杠杆率</text>
      <text class="subtitle">杠杆产品成交额 ÷ 对应正股成交额</text>
      <view v-if="report" class="hero-meta">
        <text>截至 {{ report.as_of }}</text>
        <text class="meta-dot">·</text>
        <text>覆盖 {{ coverageOk }}/{{ report.coverage.length }}</text>
      </view>
      <view v-if="report" class="hero-cache">
        <text>数据更新 {{ generatedAtLabel }}</text>
        <text :class="['cache-pill', report.cache?.is_stale && 'cache-pill-stale']">
          {{ cacheLabel }}
        </text>
      </view>
    </view>

    <view class="body">
      <view class="card control-card">
        <view class="control-group">
          <text class="control-label">时间窗口</text>
          <text class="control-hint">只裁剪已下载的历史图，不会重复拉取行情</text>
          <view class="chip-row">
            <button
              v-for="option in dayOptions"
              :key="option.value"
              :class="['chip', days === option.value && 'chip-on']"
              :aria-pressed="days === option.value"
              @click="chooseDays(option.value)"
            >
              {{ option.label }}
            </button>
          </view>
        </view>
        <view class="control-group">
          <text class="control-label">回看交易日</text>
          <text class="control-hint">按各市场共同交易日排列，可直接查看昨天、前天的完整读数</text>
          <view class="snapshot-row">
            <button
              v-for="option in snapshotOptions"
              :key="option.date"
              :class="['snapshot-chip', selectedDate === option.date && 'snapshot-chip-on']"
              :aria-pressed="selectedDate === option.date"
              @click="selectedDate = option.date"
            >
              <text class="snapshot-name">{{ option.label }}</text>
              <text class="snapshot-date">{{ option.date.slice(5) }}</text>
            </button>
          </view>
        </view>
        <view class="control-group scope-group">
          <view>
            <text class="control-label">下方读数口径</text>
            <text class="control-hint">趋势图固定同屏比较全球实线与韩国虚线</text>
          </view>
          <view class="scope-switch">
            <button
              :class="['scope-button', scope === 'all' && 'scope-button-on']"
              :aria-pressed="scope === 'all'"
              @click="scope = 'all'"
            >全部</button>
            <button
              :class="['scope-button', scope === 'kr' && 'scope-button-on']"
              :aria-pressed="scope === 'kr'"
              @click="scope = 'kr'"
            >韩国</button>
          </view>
        </view>
      </view>

      <view v-if="loading && !report" class="loading-stack" role="status">
        <view class="card skeleton skeleton-chart" />
        <view class="card skeleton skeleton-row" />
        <view class="card skeleton skeleton-row" />
        <text class="loading-text">正在汇总全球杠杆产品成交额…</text>
      </view>

      <view v-else-if="error && !report" class="card state-card" role="alert">
        <text class="state-title">暂时取不到行情</text>
        <text class="state-copy">{{ error }}</text>
        <button class="btn-primary retry-button" @click="load(true)">重新加载</button>
      </view>

      <template v-else-if="report">
        <view v-if="error" class="stale-banner" role="status">
          <text>{{ error }}，当前展示上次成功结果。</text>
        </view>
        <view v-if="report.cache?.is_stale" class="stale-banner" role="status">
          <text>行情源暂时不可用，当前展示 {{ generatedAtLabel }} 保存的历史缓存。</text>
        </view>

        <view class="chart-card">
          <MemoryLeverageChart :series="chartSeries" :as-of="report.as_of" />
        </view>

        <view class="metrics-head">
          <text class="section-title">{{ metricsTitle }}</text>
          <text class="metrics-date">交易日 {{ selectedDate || report.as_of }}</text>
        </view>
        <view v-if="visibleSeries.length" class="metrics-grid">
          <MemoryLeverageMetricCard
            v-for="item in visibleSeries"
            :key="item.id"
            :item="item"
            :product-count="productCount(item)"
          />
        </view>
        <view v-else class="card state-card">
          <text class="state-title">当前口径没有可用序列</text>
        </view>

        <view v-if="missingCoverage" class="card coverage-card">
          <view class="coverage-icon">!</view>
          <view>
            <text class="coverage-title">部分产品行情缺失</text>
            <text class="coverage-copy">
              {{ missingCoverage }} 个标的未进入本次计算；图表仍可用，但不同日期的覆盖面可能变化。
            </text>
          </view>
        </view>

        <MemoryLeverageGuide :methodology="report.methodology" />
      </template>

      <view v-else class="card state-card">
        <text class="state-title">暂无数据</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import MemoryLeverageChart from '@/components/MemoryLeverageChart.vue'
import MemoryLeverageGuide from '@/components/MemoryLeverageGuide.vue'
import MemoryLeverageMetricCard from '@/components/MemoryLeverageMetricCard.vue'
import { quantApi } from '@/utils/api.js'
import {
  filterSeriesByDays,
  leverageProductCount,
  selectChartSeries,
  selectMemorySeries,
  selectSeriesSnapshot,
  selectSnapshotDates,
} from '@/utils/memoryLeverage.mjs'

const FETCH_DAYS = 730
const dayOptions = [
  { value: 30, label: '1月' },
  { value: 90, label: '3月' },
  { value: 365, label: '1年' },
  { value: 730, label: '2年' },
]

const days = ref(365)
const scope = ref('all')
const selectedDate = ref('')
const report = ref(null)
const loading = ref(false)
const error = ref('')

const scopeSeries = computed(() => selectMemorySeries(report.value?.series || [], scope.value))
const snapshotDates = computed(() => selectSnapshotDates(scopeSeries.value, 8))
const snapshotOptions = computed(() => snapshotDates.value.map((date, index) => ({
  date,
  label: index === 0
    ? '最新'
    : index === 1
      ? '前1交易日'
      : index === 2
        ? '前2交易日'
        : '历史',
})))
const visibleSeries = computed(() =>
  selectSeriesSnapshot(scopeSeries.value, selectedDate.value)
)
const chartSeries = computed(() =>
  filterSeriesByDays(
    selectChartSeries(report.value?.series || []),
    days.value,
    report.value?.as_of,
  )
)
const coverageOk = computed(() =>
  (report.value?.coverage || []).filter(item => item.status === 'ok').length
)
const missingCoverage = computed(() =>
  (report.value?.coverage || []).filter(item => item.status === 'missing').length
)
const metricsTitle = computed(() =>
  selectedDate.value && selectedDate.value !== snapshotDates.value[0]
    ? '历史读数'
    : '最新读数'
)
const cacheLabel = computed(() => ({
  live: '实时拉取',
  memory: '内存缓存',
  disk: '本地缓存',
  stale_disk: '过期缓存',
}[report.value?.cache?.layer] || '缓存状态未知'))
const generatedAtLabel = computed(() => formatDateTime(report.value?.generated_at))

watch(snapshotDates, dates => {
  if (!dates.includes(selectedDate.value)) {
    selectedDate.value = dates[0] || ''
  }
})

function productCount(item) {
  return leverageProductCount(report.value?.coverage || [], item)
}

function formatDateTime(value) {
  const parsed = new Date(value)
  if (!value || Number.isNaN(parsed.getTime())) return '—'
  const pad = number => String(number).padStart(2, '0')
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}`
    + ` ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
}

async function load(refresh = false) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    report.value = await quantApi.memoryLeverage(FETCH_DAYS, refresh)
    selectedDate.value = ''
  } catch {
    error.value = '行情服务暂时不可用，请稍后重试'
  } finally {
    loading.value = false
  }
}

function chooseDays(value) {
  if (days.value === value) return
  days.value = value
}

onMounted(() => load(false))
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; background: $bg; }
.hero { padding: 44rpx 32rpx 58rpx; }
.hero-topline { display: flex; justify-content: space-between; align-items: center; }
.eyebrow {
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 4rpx;
  color: rgba(255, 255, 255, 0.72);
}
.hero-refresh {
  min-width: 142rpx;
  margin: 0;
  padding: 0 22rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.35);
  border-radius: $radius-pill;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 23rpx;
  line-height: 56rpx;
}
.hero-refresh::after, .chip::after, .scope-button::after { border: 0; }
.hero-refresh[disabled] { opacity: 0.65; }
.title { display: block; margin-top: 28rpx; color: #fff; font-size: 54rpx; font-weight: 800; }
.subtitle { display: block; margin-top: 10rpx; color: rgba(255,255,255,.88); font-size: 27rpx; }
.hero-meta { display: flex; margin-top: 24rpx; color: rgba(255,255,255,.72); font-size: 22rpx; }
.meta-dot { margin: 0 12rpx; }
.hero-cache { display: flex; align-items: center; gap: 12rpx; margin-top: 12rpx; color: rgba(255,255,255,.68); font-size: 20rpx; }
.cache-pill {
  padding: 4rpx 12rpx;
  border: 1rpx solid rgba(255,255,255,.2);
  border-radius: $radius-pill;
  background: rgba(255,255,255,.10);
  color: rgba(255,255,255,.9);
  font-weight: 700;
}
.cache-pill-stale { border-color: rgba(255,202,112,.5); background: rgba(187,115,0,.35); color: #ffe1aa; }
.body { max-width: 1120px; margin: -26rpx auto 0; padding: 0 24rpx 56rpx; }
.control-card { padding: 30rpx; margin-bottom: 24rpx; }
.control-group + .control-group { padding-top: 26rpx; margin-top: 26rpx; border-top: 1rpx solid $line; }
.control-label { display: block; color: $text; font-size: 25rpx; font-weight: 700; }
.control-hint { display: block; margin-top: 5rpx; color: $text-3; font-size: 21rpx; }
.chip-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12rpx; margin-top: 18rpx; }
.chip {
  margin: 0;
  padding: 0;
  background: $surface-2;
  border: 1rpx solid transparent;
  border-radius: $radius-sm;
  color: $text-2;
  font-size: 24rpx;
  line-height: 66rpx;
}
.chip-on { color: $primary; background: rgba(79,110,247,.10); border-color: rgba(79,110,247,.22); font-weight: 700; }
.snapshot-row { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 18rpx; }
.snapshot-chip {
  min-width: 130rpx;
  margin: 0;
  padding: 12rpx 18rpx;
  border: 1rpx solid $line;
  border-radius: $radius-sm;
  background: $surface;
  color: $text-2;
  line-height: 1.25;
}
.snapshot-chip::after { border: 0; }
.snapshot-chip-on { border-color: rgba(79,110,247,.35); background: rgba(79,110,247,.10); color: $primary; }
.snapshot-name, .snapshot-date { display: block; }
.snapshot-name { font-size: 21rpx; font-weight: 700; }
.snapshot-date { margin-top: 5rpx; color: $text-3; font-size: 18rpx; font-variant-numeric: tabular-nums; }
.snapshot-chip-on .snapshot-date { color: rgba(79,110,247,.75); }
.scope-group { display: flex; align-items: center; justify-content: space-between; gap: 24rpx; }
.scope-switch { display: flex; flex: none; padding: 6rpx; background: $surface-2; border-radius: $radius-pill; }
.scope-button {
  margin: 0;
  padding: 0 22rpx;
  border-radius: $radius-pill;
  background: transparent;
  color: $text-3;
  font-size: 23rpx;
  line-height: 52rpx;
}
.scope-button-on { color: $primary; background: $surface; box-shadow: 0 3rpx 10rpx rgba(40,50,90,.10); font-weight: 700; }
.metrics-head { display: flex; align-items: flex-start; justify-content: space-between; }
.section-title { display: block; color: $text; font-size: 31rpx; font-weight: 800; }
.section-note { display: block; margin-top: 7rpx; color: $text-3; font-size: 22rpx; }
.chart-card { overflow: hidden; margin-bottom: 24rpx; }
.metrics-head { align-items: baseline; margin: 34rpx 8rpx 18rpx; }
.metrics-date { color: $text-3; font-size: 21rpx; }
.metrics-grid { display: grid; grid-template-columns: 1fr; gap: 18rpx; }
.coverage-card { display: flex; gap: 20rpx; padding: 26rpx; margin-top: 24rpx; border: 1rpx solid #f7d79b; background: #fffaf0; }
.coverage-icon { width: 42rpx; height: 42rpx; flex: none; border-radius: 50%; background: #f4a42b; color: #fff; text-align: center; font-weight: 800; line-height: 42rpx; }
.coverage-title { display: block; color: #8a570d; font-size: 24rpx; font-weight: 700; }
.coverage-copy { display: block; margin-top: 5rpx; color: #9b6c28; font-size: 21rpx; line-height: 1.55; }
.state-card { padding: 58rpx 30rpx; text-align: center; }
.state-title { display: block; color: $text; font-size: 29rpx; font-weight: 800; }
.state-copy { display: block; margin-top: 12rpx; color: $text-2; font-size: 23rpx; }
.retry-button { margin-top: 28rpx; }
.stale-banner { padding: 18rpx 22rpx; margin-bottom: 20rpx; border-radius: $radius-sm; background: #fff5dc; color: #8a570d; font-size: 21rpx; }
.loading-stack { position: relative; }
.skeleton { margin-bottom: 20rpx; background: linear-gradient(90deg, #fff 20%, #f0f2f8 45%, #fff 70%); background-size: 240% 100%; animation: shimmer 1.4s infinite; }
.skeleton-chart { height: 520rpx; }
.skeleton-row { height: 190rpx; }
.loading-text { display: block; margin-top: 22rpx; color: $text-3; font-size: 22rpx; text-align: center; }
@keyframes shimmer { to { background-position: -240% 0; } }

@media (min-width: 768px) {
  .hero { padding-left: max(32px, calc((100% - 1120px) / 2)); padding-right: max(32px, calc((100% - 1120px) / 2)); }
  .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric-card:last-child:nth-child(odd) { grid-column: span 2; }
}
</style>
