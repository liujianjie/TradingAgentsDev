<template>
  <view class="page">
    <view class="grad-header header">
      <text class="title">产业链研究</text>
      <text class="subtitle">Serenity 式卡点扫描 · 优先研究清单</text>
    </view>

    <view class="body">
      <!-- 模式切换 -->
      <view class="card mode-card">
        <text class="card-title">研究模式</text>
        <view class="mode-row">
          <view
            v-for="m in modes"
            :key="m.value"
            :class="['mode-chip', mode === m.value && 'mode-chip-on']"
            @click="mode = m.value"
          >
            <text>{{ m.label }}</text>
          </view>
        </view>
        <text class="mode-hint">{{ modeHint }}</text>
      </view>

      <!-- 主体表单 -->
      <view class="card form-card">
        <view class="field">
          <text class="label">市场</text>
          <picker :range="marketOptions" :range-key="'label'" @change="onMarketChange">
            <view class="picker-row">
              <text class="picker-val">{{ marketLabel }}</text>
              <text class="picker-arrow">▾</text>
            </view>
          </picker>
        </view>

        <view v-if="mode === 'theme_scan'" class="field">
          <text class="label">主题</text>
          <input
            class="text-input"
            v-model="theme"
            placeholder="如：AI 半导体 / 机器人 / 光通信 CPO"
            placeholder-class="ph"
          />
        </view>

        <view v-else class="field">
          <text class="label">{{ mode === 'single_challenge' ? '股票代码' : '股票代码（逗号分隔）' }}</text>
          <input
            class="text-input"
            v-model="tickersInput"
            :placeholder="mode === 'single_challenge' ? '如：NVDA 或 600519.SS' : '如：NVDA, AMD, AVGO'"
            placeholder-class="ph"
          />
        </view>

        <view class="field">
          <text class="label">时间窗口（月）</text>
          <picker :range="windowOptions" @change="onWindowChange">
            <view class="picker-row">
              <text class="picker-val">{{ timeWindow }} 个月</text>
              <text class="picker-arrow">▾</text>
            </view>
          </picker>
        </view>

        <view class="cost-tip">
          <text class="cost-icon">⏱</text>
          <text class="cost-text">单次研究约 30-120 秒，调用 LLM 50-200K tokens</text>
        </view>

        <button
          class="btn-primary submit-btn"
          :disabled="!canSubmit || submitting"
          @click="handleSubmit"
        >
          {{ submitting ? '提交中...' : '开始研究' }}
        </button>
      </view>

      <!-- 最近 5 次 -->
      <view class="card recent-card" v-if="recentJobs.length">
        <text class="card-title">最近研究</text>
        <view
          v-for="j in recentJobs"
          :key="j.job_id"
          class="recent-item"
          @click="openReport(j.job_id)"
        >
          <view class="recent-head">
            <text class="recent-title">{{ recentTitle(j) }}</text>
            <text :class="['recent-status', `status-${j.status}`]">{{ statusText(j.status) }}</text>
          </view>
          <text class="recent-meta">{{ shortTime(j.created_at) }} · {{ j.request?.market }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { serenityApi } from '@/utils/api.js'

const modes = [
  { value: 'theme_scan', label: '主题扫描' },
  { value: 'single_challenge', label: '公司挑战' },
  { value: 'candidate_compare', label: '候选比较' },
]
const mode = ref('theme_scan')
const modeHint = computed(() => ({
  theme_scan: '给主题 + 市场，AI 拆产业链 + 排卡点 + 输出优先研究清单',
  single_challenge: '给一个公司，挑战它在产业链卡点的真实位置和证据',
  candidate_compare: '给几个候选，按卡点紧度 / 证据 / 估值排序',
}[mode.value]))

const marketOptions = [
  { label: 'A 股', value: 'A-share' },
  { label: '美股', value: 'US' },
  { label: '港股', value: 'HK' },
]
const market = ref('A-share')
const marketLabel = computed(() =>
  marketOptions.find(m => m.value === market.value)?.label || ''
)
function onMarketChange(e) {
  market.value = marketOptions[e.detail.value]?.value || 'A-share'
}

const theme = ref('')
const tickersInput = ref('')
const windowOptions = [3, 6, 12, 18, 24, 36]
const timeWindow = ref(12)
function onWindowChange(e) {
  timeWindow.value = windowOptions[e.detail.value] || 12
}

const submitting = ref(false)
const recentJobs = ref([])

const canSubmit = computed(() => {
  if (mode.value === 'theme_scan') return !!theme.value.trim()
  return !!tickersInput.value.trim()
})

function parseTickers(s) {
  return s.split(/[,，\s]+/).map(t => t.trim()).filter(Boolean)
}

async function handleSubmit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  const payload = {
    mode: mode.value,
    market: market.value,
    time_window_months: timeWindow.value,
  }
  if (mode.value === 'theme_scan') {
    payload.theme = theme.value.trim()
  } else {
    payload.tickers = parseTickers(tickersInput.value)
    if (!payload.tickers.length) {
      uni.showToast({ title: '请填股票代码', icon: 'none' })
      submitting.value = false
      return
    }
  }
  try {
    const r = await serenityApi.scan(payload)
    uni.showToast({ title: '已提交', icon: 'success' })
    setTimeout(() => {
      uni.navigateTo({ url: `/pages/serenity/report?jobId=${r.job_id}` })
    }, 600)
  } catch (e) {
    uni.showToast({ title: '提交失败：' + (e.message || e).slice(0, 60), icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function openReport(jobId) {
  uni.navigateTo({ url: `/pages/serenity/report?jobId=${jobId}` })
}

function recentTitle(j) {
  const req = j.request || {}
  if (req.theme) return req.theme
  if (req.tickers?.length) return req.tickers.join(' / ')
  return j.job_id
}
function statusText(s) {
  return { queued: '排队', running: '运行', completed: '已完成', failed: '失败' }[s] || s
}
function shortTime(iso) {
  if (!iso) return ''
  return iso.replace('T', ' ').slice(0, 16)
}

async function loadRecent() {
  try {
    const r = await serenityApi.listJobs()
    recentJobs.value = (r.jobs || []).slice(0, 5)
  } catch {}
}

onMounted(() => { loadRecent() })
onShow(() => { loadRecent() })
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; }

.header { padding: 56rpx 32rpx 48rpx; }
.title { font-size: 52rpx; font-weight: 800; color: #fff; }
.subtitle {
  display: block; margin-top: 14rpx;
  font-size: 26rpx; color: rgba(255,255,255,0.85);
}

.body { padding: 0 24rpx; margin-top: -24rpx; }

.card-title {
  display: block;
  font-size: 32rpx; font-weight: 700; color: $text;
  margin-bottom: 24rpx;
}

.mode-card, .form-card, .recent-card { padding: 32rpx; margin-bottom: 24rpx; }

.mode-row { display: flex; gap: 16rpx; flex-wrap: wrap; }
.mode-chip {
  padding: 16rpx 28rpx;
  background: $surface-2;
  border-radius: $radius-pill;
  font-size: 26rpx; color: $text-2;
}
.mode-chip-on { background: #4f6ef7; color: #fff; font-weight: 600; }
.mode-hint {
  display: block; margin-top: 18rpx;
  font-size: 24rpx; color: $text-3; line-height: 1.6;
}

.field { margin-bottom: 22rpx; }
.label {
  display: block; font-size: 24rpx;
  color: $text-3; margin-bottom: 10rpx;
}
.picker-row {
  background: $surface-2; border-radius: $radius-sm;
  padding: 22rpx 24rpx;
  display: flex; justify-content: space-between; align-items: center;
}
.picker-val { font-size: 28rpx; color: $text; }
.picker-arrow { font-size: 24rpx; color: $text-3; }

.text-input {
  background: $surface-2; border-radius: $radius-sm;
  padding: 22rpx 24rpx;
  font-size: 28rpx; color: $text;
}
.ph { color: $text-3; }

.cost-tip {
  display: flex; gap: 10rpx; align-items: center;
  margin: 12rpx 0 20rpx;
  font-size: 22rpx; color: $text-3;
}
.cost-icon { font-size: 26rpx; }

.submit-btn { width: 100%; padding: 24rpx; font-size: 30rpx; }

.recent-item {
  padding: 22rpx 0;
  border-top: 1rpx solid #eef0f5;
}
.recent-item:first-of-type { border-top: none; }
.recent-head {
  display: flex; justify-content: space-between; align-items: center;
}
.recent-title { font-size: 28rpx; font-weight: 600; color: $text; flex: 1; }
.recent-status {
  font-size: 22rpx; padding: 4rpx 16rpx; border-radius: $radius-pill;
}
.status-queued, .status-running { background: #fef3c7; color: #a16207; }
.status-completed { background: #dcfce7; color: #15803d; }
.status-failed { background: #fee2e2; color: #b91c1c; }
.recent-meta { display: block; margin-top: 6rpx; font-size: 22rpx; color: $text-3; }
</style>
