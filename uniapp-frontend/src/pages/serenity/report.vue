<template>
  <view class="page">
    <!-- 顶部进度 -->
    <view class="grad-header header">
      <view class="head-row">
        <text class="head-title">{{ headTitle }}</text>
        <text :class="['status-pill', `status-${status}`]">{{ statusText }}</text>
      </view>
      <view class="steps-bar">
        <view
          v-for="s in steps"
          :key="s.step"
          :class="[
            'step-dot',
            currentStep >= s.step && 'step-dot-on',
            currentStep === s.step && status === 'running' && 'step-dot-pulse',
          ]"
        ></view>
      </view>
      <text class="step-label">第 {{ currentStep }}/9 步 · {{ currentStage }}</text>
    </view>

    <view class="body" v-if="status === 'failed'">
      <view class="card error-card">
        <text class="error-title">研究失败</text>
        <text class="error-msg">{{ error }}</text>
        <button class="btn-primary back-btn" @click="back">返回重试</button>
      </view>
    </view>

    <view class="body" v-else-if="status !== 'completed'">
      <view class="card running-card">
        <text class="running-title">⏳ 研究进行中</text>
        <text class="running-hint">单次研究约 30-120 秒，涉及多次 web 搜索与 filings 查询，请稍候</text>
        <view v-if="traceLog.length" class="trace">
          <text class="trace-title">实时轨迹（最近 6 条）</text>
          <text v-for="(line, i) in traceLog.slice(-6)" :key="i" class="trace-line">{{ line }}</text>
        </view>
      </view>
    </view>

    <view class="body" v-else>
      <!-- Scope -->
      <view class="card">
        <text class="card-title">研究范围</text>
        <view class="meta-row"><text class="meta-k">市场</text><text class="meta-v">{{ result.scope.market }}</text></view>
        <view v-if="result.scope.theme" class="meta-row"><text class="meta-k">主题</text><text class="meta-v">{{ result.scope.theme }}</text></view>
        <view v-if="result.scope.tickers?.length" class="meta-row"><text class="meta-k">标的</text><text class="meta-v">{{ result.scope.tickers.join(' / ') }}</text></view>
        <view class="meta-row"><text class="meta-k">时间窗</text><text class="meta-v">{{ result.scope.time_window }}</text></view>
        <view class="meta-row"><text class="meta-k">已查源</text><text class="meta-v">{{ sourcesConsulted }} 条 · 候选 {{ candidatesInspected }} 家</text></view>
      </view>

      <!-- 系统变化 -->
      <view class="card">
        <text class="card-title">驱动逻辑（系统变化）</text>
        <text class="prose">{{ result.system_change }}</text>
      </view>

      <!-- 产业链层级 -->
      <view class="card">
        <text class="card-title">产业链层级排序</text>
        <view v-for="(l, i) in result.value_chain_layers" :key="i" class="layer-row">
          <text class="layer-rank">{{ l.rank }}</text>
          <view class="layer-body">
            <text class="layer-name">{{ l.name }}</text>
            <text class="layer-reason">{{ l.reason }}</text>
          </view>
        </view>
      </view>

      <!-- 卡点环节 -->
      <view class="card">
        <text class="card-title">卡住的环节</text>
        <view v-for="(s, i) in result.scarce_layers" :key="i" class="scarce-row">
          <view class="scarce-head">
            <text class="scarce-name">{{ s.layer }}</text>
            <text :class="['evi-tag', `evi-${s.evidence_strength}`]">{{ evidenceText(s.evidence_strength) }}</text>
          </view>
          <text class="prose">{{ s.why_scarce }}</text>
        </view>
      </view>

      <!-- 优先研究清单（核心） -->
      <view class="card priority-card">
        <text class="card-title">优先研究清单 · {{ result.top_priorities.length }} 家</text>
        <view v-for="(p, i) in result.top_priorities" :key="i" class="priority-item">
          <view class="prio-head">
            <view>
              <text class="prio-ticker">{{ p.ticker }}</text>
              <text class="prio-company">{{ p.company }}</text>
            </view>
            <view v-if="p.score" class="score-block">
              <text class="score-val">{{ p.score.final.toFixed(1) }}</text>
              <text class="score-verdict">{{ p.score.verdict }}</text>
            </view>
          </view>
          <view class="prio-row"><text class="prio-k">卡住的环节</text><text class="prio-v">{{ p.constrains_what }}</text></view>
          <view class="prio-row"><text class="prio-k">产业链位置</text><text class="prio-v">{{ p.chain_position }}</text></view>
          <view class="prio-row"><text class="prio-k">排序原因</text><text class="prio-v">{{ p.rank_reason }}</text></view>
          <view class="prio-row"><text class="prio-k">主要风险</text><text class="prio-v risk-text">{{ p.main_risk }}</text></view>
          <view class="evidence-block">
            <text class="evidence-title">证据 · {{ p.evidence.length }} 条</text>
            <view v-for="(e, j) in p.evidence" :key="j" class="evidence-item">
              <text :class="['evi-tag', `evi-${e.strength}`]">{{ strengthText(e.strength) }}</text>
              <view class="evidence-body">
                <text class="evidence-claim">{{ e.claim }}</text>
                <text v-if="isUrl(e.source)" class="evidence-link" @click="openLink(e.source)">{{ e.source }}</text>
                <text v-else class="evidence-src">{{ e.source }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 公司池 -->
      <view class="card">
        <view class="card-head" @click="universeOpen = !universeOpen">
          <text class="card-title">候选公司池 · {{ result.company_universe.length }} 家</text>
          <text class="fold-arrow">{{ universeOpen ? '▴' : '▾' }}</text>
        </view>
        <view v-if="universeOpen">
          <view v-for="(c, i) in result.company_universe" :key="i" class="universe-item">
            <view class="universe-head">
              <text class="universe-ticker">{{ c.ticker }}</text>
              <text class="universe-company">{{ c.company }}</text>
            </view>
            <text class="universe-pos">{{ c.chain_position }}</text>
            <text :class="['class-tag', `class-${c.classification}`]">{{ classText(c.classification) }}</text>
          </view>
        </view>
      </view>

      <!-- 反方理由 -->
      <view class="card">
        <text class="card-title">反方理由 / 最大风险</text>
        <view v-for="(r, i) in result.what_could_go_wrong" :key="i" class="risk-row">
          <text class="risk-dot">⚠</text>
          <text class="prose">{{ r }}</text>
        </view>
      </view>

      <!-- 下一步检查 -->
      <view class="card">
        <text class="card-title">下一步检查清单</text>
        <view v-for="(m, i) in result.next_research_moves" :key="i" class="move-row">
          <view :class="['check-box', checkedMoves[i] && 'check-box-on']" @click="toggleMove(i)">
            <text v-if="checkedMoves[i]" class="check-mark">✓</text>
          </view>
          <text :class="['move-text', checkedMoves[i] && 'move-text-done']">{{ m }}</text>
        </view>
        <text class="checklist-hint">本会话内勾选状态不持久化（v1）</text>
      </view>

      <view class="footer">
        <text class="muted">Research support only · 不构成交易建议</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { serenityApi } from '@/utils/api.js'

const steps = [
  { step: 1, name: 'set_scope' }, { step: 2, name: 'translate_story' },
  { step: 3, name: 'map_value_chain' }, { step: 4, name: 'find_scarce_layer' },
  { step: 5, name: 'build_company_universe' }, { step: 6, name: 'gather_evidence' },
  { step: 7, name: 'rank_priorities' }, { step: 8, name: 'explain_risks' },
  { step: 9, name: 'next_research_moves' },
]

const jobId = ref('')
const status = ref('queued')
const currentStep = ref(0)
const currentStage = ref('排队中')
const result = ref(null)
const error = ref('')
const sourcesConsulted = ref(0)
const candidatesInspected = ref(0)
const traceLog = ref([])
const universeOpen = ref(false)
const checkedMoves = ref({})

let pollTimer = null

const statusText = computed(() =>
  ({ queued: '排队', running: '运行中', completed: '已完成', failed: '失败' }[status.value] || status.value)
)
const headTitle = computed(() => {
  if (!result.value) return '研究中...'
  const s = result.value.scope
  if (s.theme) return s.theme
  if (s.tickers?.length) return s.tickers.join(' / ')
  return jobId.value
})

function evidenceText(s) { return { strong: '证据强', medium: '证据中', weak: '证据弱' }[s] || s }
function strengthText(s) {
  return { primary: '一手', media: '媒体', analysis: '分析', social: '社交', unverified: '待证' }[s] || s
}
function classText(c) {
  return {
    controls_scarce_layer: '控制卡点',
    supplies_scarce_layer: '供给卡点',
    benefits_from_trend: '主题受益',
    weak_control: '弱控制',
    story_only: '蹭主题',
  }[c] || c
}
function isUrl(s) { return /^https?:\/\//.test(s || '') }
function openLink(url) {
  // #ifdef H5
  window.open(url, '_blank')
  // #endif
  // #ifndef H5
  uni.setClipboardData({ data: url, success: () => uni.showToast({ title: '链接已复制', icon: 'none' }) })
  // #endif
}
function toggleMove(i) { checkedMoves.value = { ...checkedMoves.value, [i]: !checkedMoves.value[i] } }
function back() { uni.navigateBack() }

async function poll() {
  if (!jobId.value) return
  try {
    const j = await serenityApi.getJob(jobId.value)
    status.value = j.status
    currentStep.value = j.progress?.step || 0
    currentStage.value = j.progress?.stage || '排队中'
    traceLog.value = j.trace_log || []
    sourcesConsulted.value = j.sources_consulted || 0
    candidatesInspected.value = j.candidates_inspected || 0
    if (j.status === 'completed' && j.result) {
      result.value = j.result
      stopPolling()
    } else if (j.status === 'failed') {
      error.value = j.error || '未知错误'
      stopPolling()
    }
  } catch (e) {
    error.value = e.message || String(e)
    status.value = 'failed'
    stopPolling()
  }
}

function startPolling() {
  poll()
  pollTimer = setInterval(poll, 3000)
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

onMounted(() => {
  const pages = getCurrentPages()
  const opts = pages[pages.length - 1]?.options || {}
  jobId.value = opts.jobId || ''
  if (jobId.value) startPolling()
  else { status.value = 'failed'; error.value = '缺少 jobId 参数' }
})
onUnmounted(() => stopPolling())
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; }

.header { padding: 48rpx 32rpx 36rpx; }
.head-row {
  display: flex; justify-content: space-between; align-items: center;
}
.head-title {
  font-size: 40rpx; font-weight: 700; color: #fff; flex: 1;
  margin-right: 16rpx;
}
.status-pill {
  font-size: 22rpx; padding: 6rpx 18rpx; border-radius: $radius-pill;
  background: rgba(255,255,255,0.25); color: #fff;
}
.status-completed { background: rgba(74,222,128,0.4); }
.status-failed { background: rgba(248,113,113,0.5); }

.steps-bar {
  display: flex; gap: 12rpx; margin: 24rpx 0 14rpx;
}
.step-dot {
  flex: 1; height: 10rpx; border-radius: 6rpx;
  background: rgba(255,255,255,0.25);
}
.step-dot-on { background: #fff; }
.step-dot-pulse { animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}
.step-label { font-size: 22rpx; color: rgba(255,255,255,0.9); }

.body { padding: 0 24rpx; margin-top: -16rpx; }

.card {
  padding: 28rpx;
  margin-bottom: 20rpx;
  background: $surface; border-radius: $radius;
  box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.04);
}
.card-title {
  display: block;
  font-size: 30rpx; font-weight: 700; color: $text;
  margin-bottom: 18rpx;
}
.card-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12rpx;
}
.fold-arrow { font-size: 28rpx; color: $text-3; }

.prose { font-size: 26rpx; color: $text-2; line-height: 1.65; }

.meta-row { display: flex; padding: 8rpx 0; }
.meta-k { width: 130rpx; font-size: 24rpx; color: $text-3; }
.meta-v { flex: 1; font-size: 26rpx; color: $text; }

/* Layer */
.layer-row { display: flex; padding: 16rpx 0; border-top: 1rpx solid $line; }
.layer-row:first-of-type { border-top: none; }
.layer-rank {
  width: 56rpx; height: 56rpx; border-radius: 28rpx;
  background: $primary; color: #fff;
  font-weight: 700; font-size: 26rpx;
  text-align: center; line-height: 56rpx; margin-right: 16rpx;
}
.layer-body { flex: 1; }
.layer-name { display: block; font-size: 28rpx; font-weight: 600; color: $text; }
.layer-reason { display: block; margin-top: 4rpx; font-size: 24rpx; color: $text-2; line-height: 1.5; }

/* Scarce */
.scarce-row { padding: 14rpx 0; border-top: 1rpx solid $line; }
.scarce-row:first-of-type { border-top: none; }
.scarce-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8rpx; }
.scarce-name { font-size: 28rpx; font-weight: 600; color: $text; }
.evi-tag { font-size: 20rpx; padding: 4rpx 14rpx; border-radius: $radius-pill; }
.evi-strong, .evi-primary { background: #dcfce7; color: #15803d; }
.evi-medium, .evi-media, .evi-analysis { background: #fef3c7; color: #a16207; }
.evi-weak, .evi-social { background: #ffedd5; color: #c2410c; }
.evi-unverified { background: #f3f4f6; color: #6b7280; }

/* Priority */
.priority-card { border: 2rpx solid $primary; }
.priority-item { padding: 22rpx 0; border-top: 1rpx solid $line; }
.priority-item:first-of-type { border-top: none; padding-top: 0; }
.prio-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14rpx; }
.prio-ticker { display: block; font-size: 32rpx; font-weight: 800; color: $primary; }
.prio-company { display: block; font-size: 24rpx; color: $text-2; margin-top: 2rpx; }
.score-block { text-align: right; }
.score-val { display: block; font-size: 40rpx; font-weight: 800; color: $primary; }
.score-verdict { display: block; font-size: 20rpx; color: $text-3; }
.prio-row { display: flex; padding: 6rpx 0; }
.prio-k { width: 150rpx; font-size: 22rpx; color: $text-3; }
.prio-v { flex: 1; font-size: 26rpx; color: $text; line-height: 1.55; }
.risk-text { color: $sell; }

.evidence-block { margin-top: 14rpx; padding-top: 14rpx; border-top: 1rpx dashed $line; }
.evidence-title { display: block; font-size: 22rpx; color: $text-3; margin-bottom: 10rpx; }
.evidence-item { display: flex; gap: 12rpx; padding: 8rpx 0; }
.evidence-body { flex: 1; }
.evidence-claim { display: block; font-size: 24rpx; color: $text; line-height: 1.5; }
.evidence-link { display: block; margin-top: 4rpx; font-size: 22rpx; color: $primary; text-decoration: underline; }
.evidence-src { display: block; margin-top: 4rpx; font-size: 22rpx; color: $text-3; }

/* Universe */
.universe-item { display: flex; gap: 14rpx; align-items: center; padding: 12rpx 0; border-top: 1rpx solid $line; }
.universe-item:first-of-type { border-top: none; }
.universe-head { display: flex; gap: 8rpx; flex: 1; }
.universe-ticker { font-weight: 700; color: $text; font-size: 24rpx; }
.universe-company { color: $text-2; font-size: 24rpx; }
.universe-pos { font-size: 22rpx; color: $text-3; }
.class-tag { font-size: 20rpx; padding: 4rpx 12rpx; border-radius: $radius-pill; }
.class-controls_scarce_layer { background: #dcfce7; color: #15803d; }
.class-supplies_scarce_layer { background: #dbeafe; color: #1d4ed8; }
.class-benefits_from_trend { background: #fef3c7; color: #a16207; }
.class-weak_control { background: #ffedd5; color: #c2410c; }
.class-story_only { background: #fee2e2; color: #b91c1c; }

/* Risks */
.risk-row { display: flex; gap: 12rpx; padding: 8rpx 0; }
.risk-dot { font-size: 26rpx; }

/* Moves */
.move-row { display: flex; gap: 14rpx; align-items: center; padding: 12rpx 0; }
.check-box {
  width: 36rpx; height: 36rpx; border: 2rpx solid $text-3;
  border-radius: 8rpx; display: flex; align-items: center; justify-content: center;
}
.check-box-on { background: $primary; border-color: $primary; }
.check-mark { color: #fff; font-size: 24rpx; }
.move-text { flex: 1; font-size: 26rpx; color: $text; line-height: 1.55; }
.move-text-done { color: $text-3; text-decoration: line-through; }
.checklist-hint { display: block; margin-top: 10rpx; font-size: 20rpx; color: $text-3; }

/* Running / error */
.running-card, .error-card { padding: 40rpx 32rpx; text-align: center; }
.running-title { display: block; font-size: 32rpx; font-weight: 700; color: $text; margin-bottom: 12rpx; }
.running-hint { display: block; font-size: 24rpx; color: $text-2; line-height: 1.6; }
.trace { margin-top: 24rpx; padding-top: 18rpx; border-top: 1rpx dashed $line; text-align: left; }
.trace-title { display: block; font-size: 22rpx; color: $text-3; margin-bottom: 8rpx; }
.trace-line { display: block; font-size: 22rpx; color: $text-2; font-family: monospace; padding: 2rpx 0; }

.error-title { display: block; font-size: 30rpx; font-weight: 700; color: $sell; margin-bottom: 12rpx; }
.error-msg { display: block; font-size: 26rpx; color: $text-2; line-height: 1.6; margin-bottom: 24rpx; }
.back-btn { width: 100%; padding: 24rpx; }

.footer { padding: 24rpx 0 48rpx; text-align: center; }
.muted { font-size: 22rpx; color: $text-3; }
</style>
