<template>
  <view class="container">
    <view class="filter-bar">
      <input
        v-model="filterTicker"
        class="input"
        placeholder="按股票代码筛选（留空显示全部）"
        @confirm="reload"
      />
      <button class="btn btn-small" @click="reload">刷新</button>
    </view>

    <view v-if="loading" class="muted">加载中...</view>
    <view v-else-if="error" class="error">{{ error }}</view>
    <view v-else-if="items.length === 0" class="muted">暂无历史记录</view>

    <view v-else class="list">
      <view
        v-for="item in items"
        :key="item.jobId"
        class="row-item"
        @click="open(item.jobId, item.ticker)"
      >
        <view class="row-main">
          <text class="ticker">{{ item.ticker }}</text>
          <text :class="['status', `status-${item.status}`]">{{ statusText(item.status) }}</text>
        </view>
        <view class="row-meta">
          <text class="meta">{{ formatTime(item.createdAt) }}</text>
          <text class="meta" v-if="item.decision">{{ item.decision }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/utils/api.js'

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

function statusText(s) {
  return { queued: '排队', running: '运行', completed: '完成', failed: '失败' }[s] || s
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
.container {
  padding: 24rpx;
}
.filter-bar {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
  align-items: center;
}
.input {
  flex: 1;
  padding: 16rpx;
  border: 1rpx solid #e0e0e0;
  border-radius: 8rpx;
  font-size: 26rpx;
  background: #fff;
}
.btn {
  background: #1976d2;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  font-size: 26rpx;
}
.btn-small {
  padding: 14rpx 28rpx;
}
.list {
  background: #fff;
  border-radius: 16rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}
.row-item {
  padding: 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.row-item:last-child {
  border-bottom: none;
}
.row-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ticker {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}
.status {
  font-size: 24rpx;
  padding: 4rpx 12rpx;
  border-radius: 4rpx;
}
.status-queued, .status-running { background: #e3f2fd; color: #1976d2; }
.status-completed { background: #e8f5e9; color: #2e7d32; }
.status-failed { background: #ffebee; color: #c62828; }
.row-meta {
  margin-top: 8rpx;
  display: flex;
  justify-content: space-between;
}
.meta {
  font-size: 22rpx;
  color: #999;
}
.muted {
  text-align: center;
  color: #999;
  padding: 80rpx 0;
}
.error {
  text-align: center;
  color: #c62828;
  padding: 32rpx;
}
</style>
