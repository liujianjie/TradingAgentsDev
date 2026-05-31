<template>
  <view class="container">
    <view class="header">
      <text class="title">TradingAgents</text>
      <text class="subtitle">智能投研助手</text>
    </view>

    <view class="status-card">
      <text class="status-label">后端状态</text>
      <text :class="['status-value', isHealthy ? 'healthy' : 'unhealthy']">
        {{ statusText }}
      </text>
    </view>

    <!-- 手动触发卡片 -->
    <view class="trigger-card">
      <text class="card-title">手动触发分析</text>

      <view class="field">
        <text class="label">股票</text>
        <picker :range="tickerOptions" :range-key="'label'" @change="onPickerChange">
          <view class="picker-row">
            <text class="picker-val">{{ selectedTicker || '选择股票' }}</text>
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
        class="btn btn-primary"
        :disabled="!selectedTicker || triggering"
        @click="handleTrigger"
      >
        {{ triggering ? '触发中...' : '开始分析' }}
      </button>
    </view>

    <view class="actions">
      <button class="btn" @click="goWatchlist">管理自选股</button>
      <button class="btn" @click="goHistory">查看历史</button>
    </view>

    <view class="footer">
      <text class="muted">v0.1.0 · 阶段二</text>
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
    statusText.value = '离线（后端未启动？）'
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

onMounted(() => { checkHealth(); loadWatchlist() })
</script>

<style lang="scss" scoped>
.container {
  padding: 32rpx;
  min-height: 100vh;
}
.header {
  text-align: center;
  padding: 48rpx 0 32rpx;
}
.title {
  display: block;
  font-size: 48rpx;
  font-weight: 700;
  color: #1976d2;
}
.subtitle {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #666;
}
.status-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.status-label { font-size: 28rpx; color: #666; }
.status-value { font-size: 30rpx; font-weight: 600; }
.healthy { color: #4caf50; }
.unhealthy { color: #f44336; }

.trigger-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,.05);
}
.card-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 24rpx;
}
.field {
  margin-bottom: 20rpx;
}
.label {
  display: block;
  font-size: 24rpx;
  color: #888;
  margin-bottom: 8rpx;
}
.picker-row {
  background: #f5f7fa;
  border-radius: 10rpx;
  padding: 20rpx 24rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.picker-val { font-size: 28rpx; color: #333; }
.picker-arrow { font-size: 24rpx; color: #999; }

.actions {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.btn {
  background: #fff;
  border: 1rpx solid #e0e0e0;
  border-radius: 12rpx;
  padding: 22rpx;
  font-size: 30rpx;
}
.btn-primary {
  background: #1976d2;
  color: #fff;
  border-color: #1976d2;
  margin-bottom: 8rpx;
}
.btn-primary[disabled] { background: #b0bec5; border-color: #b0bec5; }

.footer {
  margin-top: 60rpx;
  text-align: center;
}
.muted { font-size: 24rpx; color: #999; }
</style>
