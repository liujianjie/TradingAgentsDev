<template>
  <view class="page">
    <!-- 渐变头 -->
    <view class="grad-header header">
      <view class="brand-row">
        <text class="title">TradingAgents</text>
        <view class="status-chip">
          <view :class="['dot', isHealthy ? 'dot-on' : 'dot-off']"></view>
          <text class="status-text">{{ statusText }}</text>
        </view>
      </view>
      <text class="subtitle">AI 多智能体 · 智能投研助手</text>
    </view>

    <view class="body">
      <!-- 手动触发卡片 -->
      <view class="card trigger-card">
        <text class="card-title">手动触发分析</text>

        <view class="field">
          <text class="label">股票</text>
          <picker :range="tickerOptions" :range-key="'label'" @change="onPickerChange">
            <view class="picker-row">
              <text :class="['picker-val', !selectedTicker && 'placeholder']">
                {{ selectedTickerLabel || '选择股票' }}
              </text>
              <text class="picker-arrow">▾</text>
            </view>
          </picker>
        </view>

        <view class="field">
          <text class="label">日期</text>
          <picker mode="date" :value="selectedDate" @change="onDateChange">
            <view class="picker-row">
              <text class="picker-val">{{ selectedDate }}</text>
              <text class="picker-arrow">▾</text>
            </view>
          </picker>
        </view>

        <button
          class="btn-primary trigger-btn"
          :disabled="!selectedTicker || triggering"
          @click="handleTrigger"
        >
          {{ triggering ? '触发中...' : '开始分析' }}
        </button>
      </view>

      <!-- 快捷入口 -->
      <view class="quick-row">
        <view class="card quick-card" @click="goWatchlist">
          <text class="quick-icon">⭐</text>
          <text class="quick-label">管理自选股</text>
        </view>
        <view class="card quick-card" @click="goHistory">
          <text class="quick-icon">🕑</text>
          <text class="quick-label">查看历史</text>
        </view>
        <view class="card quick-card" @click="goSettings">
          <text class="quick-icon">⚙️</text>
          <text class="quick-label">设置</text>
        </view>
      </view>

      <view class="footer">
        <text class="muted">v0.1.0 · 阶段二</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '@/utils/api.js'

const isHealthy = ref(false)
const statusText = ref('检查中...')
const watchlist = ref([])
const triggering = ref(false)
const selectedDate = ref(todayStr())

const tickerOptions = computed(() =>
  watchlist.value.map(w => ({ label: `${w.ticker}  ${w.name || ''}`.trim(), value: w.ticker }))
)
const selectedTicker = ref('')
const selectedTickerLabel = computed(() =>
  tickerOptions.value.find(o => o.value === selectedTicker.value)?.label || '')

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function onPickerChange(e) {
  selectedTicker.value = tickerOptions.value[e.detail.value]?.value || ''
}

function onDateChange(e) {
  selectedDate.value = e.detail.value
}

async function handleTrigger() {
  if (!selectedTicker.value || triggering.value) return
  triggering.value = true
  try {
    const r = await api.triggerAnalysis(selectedTicker.value, selectedDate.value)
    uni.showToast({ title: '已触发', icon: 'success' })
    setTimeout(() => {
      uni.navigateTo({
        url: `/pages/analysis/index?jobId=${r.jobId}&ticker=${selectedTicker.value}`
      })
    }, 800)
  } catch (e) {
    uni.showToast({ title: '触发失败：' + (e.message || e).slice(0, 50), icon: 'none' })
  } finally {
    triggering.value = false
  }
}

async function checkHealth() {
  statusText.value = '检查中...'
  try {
    const r = await api.health()
    isHealthy.value = r?.status === 'ok'
    statusText.value = isHealthy.value ? '在线' : '异常'
  } catch {
    isHealthy.value = false
    statusText.value = '离线'
  }
}

async function loadWatchlist() {
  try {
    watchlist.value = await api.getWatchlist()
    if (watchlist.value.length) selectedTicker.value = watchlist.value[0].ticker
  } catch {}
}

function goWatchlist() { uni.switchTab({ url: '/pages/watchlist/index' }) }
function goHistory() { uni.switchTab({ url: '/pages/history/index' }) }
function goSettings() { uni.navigateTo({ url: '/pages/settings/index' }) }

onMounted(() => { checkHealth(); loadWatchlist() })
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; }

/* 渐变头 */
.header {
  padding: 56rpx 32rpx 48rpx;
}
.brand-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title {
  font-size: 52rpx;
  font-weight: 800;
  color: #fff;
  letter-spacing: 1rpx;
}
.subtitle {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.85);
}
.status-chip {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: rgba(255, 255, 255, 0.18);
  padding: 8rpx 20rpx;
  border-radius: $radius-pill;
}
.dot { width: 14rpx; height: 14rpx; border-radius: 50%; }
.dot-on { background: #4ade80; box-shadow: 0 0 8rpx #4ade80; }
.dot-off { background: #f87171; }
.status-text { font-size: 24rpx; color: #fff; }

/* 主体（上移盖住渐变头底部，做出层次） */
.body {
  padding: 0 24rpx;
  margin-top: -24rpx;
}

.trigger-card {
  padding: 32rpx;
  margin-bottom: 24rpx;
}
.card-title {
  display: block;
  font-size: 32rpx;
  font-weight: 700;
  color: $text;
  margin-bottom: 24rpx;
}
.field { margin-bottom: 22rpx; }
.label {
  display: block;
  font-size: 24rpx;
  color: $text-3;
  margin-bottom: 10rpx;
}
.picker-row {
  background: $surface-2;
  border-radius: $radius-sm;
  padding: 22rpx 24rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.picker-val { font-size: 28rpx; color: $text; }
.picker-val.placeholder { color: $text-3; }
.picker-arrow { font-size: 24rpx; color: $text-3; }
.trigger-btn { width: 100%; padding: 24rpx; font-size: 30rpx; margin-top: 8rpx; }

/* 快捷入口 */
.quick-row { display: flex; gap: 20rpx; }
.quick-card {
  flex: 1;
  padding: 36rpx 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
}
.quick-icon { font-size: 48rpx; }
.quick-label { font-size: 28rpx; color: $text-2; font-weight: 600; }

.footer { margin-top: 56rpx; text-align: center; }
.muted { font-size: 24rpx; color: $text-3; }
</style>
