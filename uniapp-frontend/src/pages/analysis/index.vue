<template>
  <view class="container">
    <view class="header-card">
      <text class="ticker">{{ ticker || '—' }}</text>
      <text class="job-id">任务 {{ jobId.slice(0, 8) }}...</text>
    </view>

    <view :class="['status-card', `status-${status}`]">
      <text class="status-label">状态</text>
      <text class="status-value">{{ statusText }}</text>
      <view v-if="status === 'queued' || status === 'running'" class="running-info">
        <view class="spinner-row">
          <view class="spinner"></view>
          <text class="hint-text">{{ runningHint }}</text>
        </view>
        <text class="elapsed">已等待 {{ elapsedMin }} 分钟，分析通常需要 10-30 分钟</text>
      </view>
    </view>

    <view v-if="error" class="error-card">
      <text class="error-title">错误</text>
      <text class="error-body">{{ error }}</text>
    </view>

    <view v-if="result && status === 'completed'" class="report">
      <view v-if="result.finalTradeDecision" class="section">
        <text class="section-title">📊 最终决策</text>
        <text class="section-body">{{ result.finalTradeDecision }}</text>
      </view>
      <view v-if="result.investmentPlan" class="section">
        <text class="section-title">💼 投资计划</text>
        <text class="section-body">{{ result.investmentPlan }}</text>
      </view>
      <view v-if="result.marketReport" class="section">
        <text class="section-title">📈 技术面</text>
        <text class="section-body">{{ result.marketReport }}</text>
      </view>
      <view v-if="result.sentimentReport" class="section">
        <text class="section-title">💬 情感面</text>
        <text class="section-body">{{ result.sentimentReport }}</text>
      </view>
      <view v-if="result.newsReport" class="section">
        <text class="section-title">📰 新闻面</text>
        <text class="section-body">{{ result.newsReport }}</text>
      </view>
      <view v-if="result.fundamentalsReport" class="section">
        <text class="section-title">🏢 基本面</text>
        <text class="section-body">{{ result.fundamentalsReport }}</text>
      </view>
    </view>

    <view class="actions" v-if="status === 'completed' || status === 'failed'">
      <button class="btn" @click="goBack">返回</button>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '@/utils/api.js'

const jobId = ref('')
const ticker = ref('')
const status = ref('queued')
const progress = ref(0)
const result = ref(null)
const error = ref('')
const startTime = ref(Date.now())

let pollTimer = null
let hintTimer = null

const HINTS = [
  '正在获取市场数据...',
  '技术面 Agent 分析中...',
  '情感面 Agent 分析中...',
  '新闻面 Agent 分析中...',
  '基本面 Agent 分析中...',
  '多空辩论中...',
  '风险评估中...',
  '生成最终决策...',
]
const hintIdx = ref(0)
const runningHint = computed(() => HINTS[hintIdx.value % HINTS.length])
const elapsedMin = computed(() => Math.floor((Date.now() - startTime.value) / 60000))

const statusText = computed(() => {
  return {
    queued: '排队中',
    running: '分析中',
    completed: '已完成',
    failed: '失败',
  }[status.value] || status.value
})

onLoad((options) => {
  jobId.value = options?.jobId || ''
  ticker.value = options?.ticker || ''
  startTime.value = Date.now()
  if (jobId.value) {
    poll()
    pollTimer = setInterval(poll, 5000)
    hintTimer = setInterval(() => { hintIdx.value++ }, 4000)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (hintTimer) clearInterval(hintTimer)
})

async function poll() {
  if (!jobId.value) return
  try {
    const job = await api.getJob(jobId.value)
    status.value = job.status
    progress.value = job.progress || 0
    result.value = job.result
    error.value = job.error || ''
    if (status.value === 'completed' || status.value === 'failed') {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
      if (hintTimer) { clearInterval(hintTimer); hintTimer = null }
    }
  } catch (e) {
    error.value = '查询任务失败：' + (e.message || e)
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

<style lang="scss" scoped>
.container {
  padding: 24rpx;
}
.header-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  text-align: center;
}
.ticker {
  display: block;
  font-size: 48rpx;
  font-weight: 700;
  color: #1976d2;
}
.job-id {
  display: block;
  font-size: 22rpx;
  color: #999;
  margin-top: 8rpx;
}

.status-card {
  border-radius: 16rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  background: #fff;
}
.status-card.status-queued, .status-card.status-running {
  background: #e3f2fd;
}
.status-card.status-completed {
  background: #e8f5e9;
}
.status-card.status-failed {
  background: #ffebee;
}
.status-label {
  font-size: 24rpx;
  color: #666;
}
.status-value {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  margin-top: 8rpx;
}

.progress-bar {
  margin-top: 16rpx;
  height: 8rpx;
  background: #e0e0e0;
  border-radius: 4rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #1976d2;
  transition: width 0.3s;
}

.error-card {
  background: #ffebee;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}
.error-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #c62828;
}
.error-body {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #c62828;
  word-break: break-all;
}

.section {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
}
.section-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 12rpx;
}
.section-body {
  display: block;
  font-size: 26rpx;
  color: #555;
  line-height: 1.6;
  white-space: pre-wrap;
}

.running-info {
  margin-top: 16rpx;
}
.spinner-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.spinner {
  width: 32rpx;
  height: 32rpx;
  border: 4rpx solid #bbdefb;
  border-top-color: #1976d2;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.hint-text {
  font-size: 26rpx;
  color: #1976d2;
}
.elapsed {
  display: block;
  margin-top: 12rpx;
  font-size: 22rpx;
  color: #90a4ae;
}

.actions {
  margin-top: 32rpx;
  text-align: center;
}
.btn {
  background: #1976d2;
  color: #fff;
  padding: 20rpx 64rpx;
  border-radius: 8rpx;
  font-size: 28rpx;
  border: none;
}
</style>
