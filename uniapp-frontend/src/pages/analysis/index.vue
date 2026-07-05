<template>
  <view class="container">
    <!-- 渐变信号头 -->
    <view class="grad-header header">
      <view class="header-top">
        <text class="ticker">{{ ticker || '—' }}</text>
        <view v-if="status === 'completed' && signal" :class="['pill', `pill-${signal.key}`, 'sig']">
          {{ signal.label }}
        </view>
        <view v-else-if="status === 'completed'" class="pill pill-muted sig">已完成</view>
      </view>
      <text class="job-meta">任务 {{ jobId.slice(0, 8) }} · {{ statusText }}</text>
    </view>

    <!-- 运行中 -->
    <view v-if="status === 'queued' || status === 'running'" class="card running-card">
      <view class="spinner-row">
        <view class="spinner"></view>
        <text class="hint-text">{{ runningHint }}</text>
      </view>
      <text class="elapsed">已等待 {{ elapsedMin }} 分钟 · 分析通常需要 10–30 分钟</text>
    </view>

    <!-- 失败 -->
    <view v-if="error" class="card error-card">
      <text class="error-title">分析失败</text>
      <text class="error-body">{{ error }}</text>
    </view>

    <!-- 报告（MD 渲染，可折叠） -->
    <view v-if="result && status === 'completed'" class="report">
      <view v-for="sec in sections" :key="sec.key" class="card section">
        <view class="section-head" @click="toggle(sec.key)">
          <text class="section-title">{{ sec.icon }} {{ sec.title }}</text>
          <text class="chevron">{{ openMap[sec.key] ? '−' : '+' }}</text>
        </view>
        <view v-if="openMap[sec.key]" class="section-body">
          <mp-html :content="htmlMap[sec.key]" :selectable="true" />
        </view>
      </view>
    </view>

    <!-- 报告保存路径提示 -->
    <view v-if="status === 'completed' && result?.reportPath" class="card save-hint">
      <text class="save-icon">💾</text>
      <text class="save-label">报告已保存至</text>
      <text class="save-path" selectable="true">{{ result.reportPath }}</text>
    </view>

    <view class="actions" v-if="status === 'completed' || status === 'failed'">
      <button
        v-if="status === 'completed'"
        class="btn-primary actbtn push-btn"
        :disabled="pushing || pushed"
        @click="handlePush"
      >
        {{ pushed ? '✓ 已推送' : (pushing ? '推送中...' : '📲 推送到手机') }}
      </button>
      <button class="btn-ghost actbtn" @click="goBack">返回</button>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '@/utils/api.js'
import { renderMarkdown, parseSignal } from '@/utils/markdown.js'

const jobId = ref('')
const ticker = ref('')
const status = ref('queued')
const result = ref(null)
const error = ref('')
const startTime = ref(Date.now())
const pushing = ref(false)
const pushed = ref(false)

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

const statusText = computed(() => ({
  queued: '排队中',
  running: '分析中',
  completed: '已完成',
  failed: '失败',
}[status.value] || status.value))

const signal = computed(() =>
  parseSignal(result.value?.decision || result.value?.finalTradeDecision))

// 每个分析维度对应的 markdown → HTML
const htmlMap = computed(() => {
  const r = result.value || {}
  return {
    decision: renderMarkdown(r.finalTradeDecision),
    plan: renderMarkdown(r.investmentPlan),
    market: renderMarkdown(r.marketReport),
    sentiment: renderMarkdown(r.sentimentReport),
    news: renderMarkdown(r.newsReport),
    fundamentals: renderMarkdown(r.fundamentalsReport),
    sources: renderMarkdown(r.dataSources),
  }
})

const SECTION_META = [
  { key: 'decision', icon: '🎯', title: '最终决策' },
  { key: 'plan', icon: '💼', title: '投资计划' },
  { key: 'market', icon: '📈', title: '技术面' },
  { key: 'sentiment', icon: '💬', title: '情感面' },
  { key: 'news', icon: '📰', title: '新闻面' },
  { key: 'fundamentals', icon: '🏢', title: '基本面' },
  { key: 'sources', icon: '🔌', title: '数据源' },
]
const sections = computed(() => SECTION_META.filter(s => htmlMap.value[s.key]))

// 决策与计划默认展开，分析员报告默认折叠
const openMap = ref({
  decision: true, plan: true,
  market: false, sentiment: false, news: false, fundamentals: false,
})
function toggle(key) { openMap.value[key] = !openMap.value[key] }

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

async function handlePush() {
  if (pushing.value || pushed.value || !jobId.value) return
  pushing.value = true
  try {
    const r = await api.pushAnalysis(jobId.value)
    if (r?.success) {
      pushed.value = true
      uni.showToast({ title: '已推送到微信', icon: 'success' })
    } else {
      uni.showToast({ title: '推送失败：' + (r?.error || '未知错误').slice(0, 40), icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: '推送失败：' + (e.message || e).slice(0, 50), icon: 'none' })
  } finally {
    pushing.value = false
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

<style lang="scss" scoped>
.container {
  padding-bottom: 40rpx;
}

/* 渐变信号头 */
.header {
  padding: 40rpx 32rpx 36rpx;
  margin-bottom: 24rpx;
}
.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ticker {
  font-size: 52rpx;
  font-weight: 800;
  color: #fff;
  letter-spacing: 1rpx;
}
.sig {
  background: rgba(255, 255, 255, 0.92);
}
.job-meta {
  display: block;
  margin-top: 14rpx;
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.82);
}

/* 卡片通用边距 */
.report, .running-card, .error-card { margin: 0 24rpx; }
.running-card, .error-card { padding: 32rpx; margin-bottom: 24rpx; }

/* 运行中 */
.spinner-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.spinner {
  width: 36rpx;
  height: 36rpx;
  border: 5rpx solid #dbe2fb;
  border-top-color: $primary;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.hint-text { font-size: 28rpx; color: $primary; font-weight: 600; }
.elapsed { display: block; margin-top: 16rpx; font-size: 24rpx; color: $text-3; }

/* 失败 */
.error-card { background: $sell-bg; box-shadow: none; }
.error-title { font-size: 30rpx; font-weight: 700; color: $sell; }
.error-body {
  display: block; margin-top: 12rpx;
  font-size: 26rpx; color: $sell; word-break: break-all;
}

/* 报告分段卡片 */
.section { margin-bottom: 20rpx; overflow: hidden; }
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 32rpx;
}
.section-title { font-size: 30rpx; font-weight: 700; color: $text; }
.chevron { font-size: 40rpx; color: $text-3; line-height: 1; }
.section-body {
  padding: 0 32rpx 28rpx;
  border-top: 1rpx solid $line;
  padding-top: 20rpx;
  font-size: 27rpx;
  color: $text-2;
  line-height: 1.7;
}

/* 报告保存提示 */
.save-hint {
  margin: 0 24rpx 20rpx;
  padding: 24rpx 28rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.save-icon { font-size: 32rpx; }
.save-label { font-size: 24rpx; color: $text-3; }
.save-path {
  font-size: 22rpx;
  color: $primary;
  word-break: break-all;
  line-height: 1.5;
}

/* 操作 */
.actions { margin: 32rpx 24rpx 0; display: flex; flex-direction: column; gap: 16rpx; }
.actbtn { width: 100%; padding: 22rpx; font-size: 30rpx; }
.push-btn { /* 主推按钮，跟随主色 */ }
</style>
