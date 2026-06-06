<template>
  <view class="container">
    <view class="filter-bar">
      <input
        v-model="filterTicker"
        class="input"
        placeholder="按代码筛选，留空显示全部"
        @confirm="reload"
      />
      <button class="btn-primary btn-refresh" @click="reload">刷新</button>
    </view>

    <view v-if="loading" class="placeholder">加载中...</view>
    <view v-else-if="error" class="placeholder err">{{ error }}</view>
    <view v-else-if="items.length === 0" class="placeholder">暂无历史记录</view>

    <view v-else class="list">
      <view
        v-for="item in items"
        :key="item.jobId"
        class="card row-item"
        @click="open(item.jobId, item.ticker)"
      >
        <view class="row-main">
          <text class="ticker">{{ item.ticker }}</text>
          <view :class="['pill', signalClass(item)]">{{ signalLabel(item) }}</view>
        </view>
        <view class="row-meta">
          <text class="meta">{{ formatTime(item.createdAt) }}</text>
          <text class="meta arrow">›</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/utils/api.js'
import { parseSignal } from '@/utils/markdown.js'

const items = ref([])
const loading = ref(false)
const error = ref('')
const filterTicker = ref('')

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (filterTicker.value.trim()) {
      params.ticker = filterTicker.value.trim().toUpperCase()
    }
    items.value = await api.getHistory(params)
  } catch (e) {
    error.value = '加载失败：' + (e.message || e)
    items.value = []
  } finally {
    loading.value = false
  }
}

const STATUS_LABEL = { queued: '排队', running: '运行', completed: '完成', failed: '失败' }

// 完成且能解析出信号 → 显示买/卖/持；否则显示运行状态
function signalLabel(item) {
  if (item.status === 'completed') {
    const sig = parseSignal(item.decision)
    if (sig) return sig.label
  }
  return STATUS_LABEL[item.status] || item.status
}
function signalClass(item) {
  if (item.status === 'completed') {
    const sig = parseSignal(item.decision)
    if (sig) return `pill-${sig.key}`
  }
  if (item.status === 'failed') return 'pill-sell'
  if (item.status === 'completed') return 'pill-muted'
  return 'pill-hold'
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function open(jobId, ticker) {
  uni.navigateTo({ url: `/pages/analysis/index?jobId=${jobId}&ticker=${ticker}` })
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.container { padding: 24rpx; }

.filter-bar {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
  align-items: center;
}
.input {
  flex: 1;
  padding: 22rpx 24rpx;
  border: none;
  border-radius: $radius-sm;
  font-size: 27rpx;
  background: $surface;
  box-shadow: $shadow;
}
.btn-refresh { padding: 22rpx 36rpx; font-size: 27rpx; }

.list { display: flex; flex-direction: column; gap: 16rpx; }
.row-item { padding: 28rpx 32rpx; }
.row-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ticker { font-size: 32rpx; font-weight: 700; color: $text; letter-spacing: 1rpx; }
.row-meta {
  margin-top: 12rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.meta { font-size: 24rpx; color: $text-3; }
.arrow { font-size: 36rpx; color: $text-3; }

.placeholder {
  text-align: center;
  color: $text-3;
  padding: 100rpx 0;
  font-size: 28rpx;
}
.placeholder.err { color: $sell; }
</style>
