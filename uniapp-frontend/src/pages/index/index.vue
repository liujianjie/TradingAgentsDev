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

    <view class="actions">
      <button class="btn btn-primary" @click="goWatchlist">管理自选股</button>
      <button class="btn" @click="goHistory">查看历史</button>
      <button class="btn" @click="checkHealth">刷新状态</button>
    </view>

    <view class="footer">
      <text class="muted">v0.1.0 · 阶段二开发中</text>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/utils/api.js'

const isHealthy = ref(false)
const statusText = ref('检查中...')

async function checkHealth() {
  statusText.value = '检查中...'
  try {
    const r = await api.health()
    isHealthy.value = r?.status === 'ok'
    statusText.value = isHealthy.value ? '在线' : '异常'
  } catch (e) {
    isHealthy.value = false
    statusText.value = '离线（后端未启动？）'
  }
}

function goWatchlist() {
  uni.switchTab({ url: '/pages/watchlist/index' })
}
function goHistory() {
  uni.switchTab({ url: '/pages/history/index' })
}

onMounted(checkHealth)
</script>

<style lang="scss" scoped>
.container {
  padding: 32rpx;
  min-height: 100vh;
}
.header {
  text-align: center;
  padding: 60rpx 0;
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
  padding: 32rpx;
  margin-bottom: 32rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.status-label {
  font-size: 28rpx;
  color: #666;
}
.status-value {
  font-size: 30rpx;
  font-weight: 600;
}
.healthy { color: #4caf50; }
.unhealthy { color: #f44336; }

.actions {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}
.btn {
  background: #fff;
  border: 1rpx solid #e0e0e0;
  border-radius: 12rpx;
  padding: 24rpx;
  font-size: 30rpx;
}
.btn-primary {
  background: #1976d2;
  color: #fff;
  border-color: #1976d2;
}

.footer {
  margin-top: 80rpx;
  text-align: center;
}
.muted {
  font-size: 24rpx;
  color: #999;
}
</style>
