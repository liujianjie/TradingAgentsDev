<template>
  <view class="page">
    <view class="body">
      <!-- 推送时间 -->
      <view class="card sec">
        <text class="card-title">⏰ 推送时间</text>
        <text class="hint">定时分析自选股并微信推送（仅工作日）。关掉某档则该时段不推送。</text>

        <view class="row">
          <view class="row-left">
            <switch :checked="preEnabled" color="#4f6ef7" @change="e => preEnabled = e.detail.value" />
            <text class="row-label">盘前</text>
          </view>
          <picker mode="time" :value="preTime" :disabled="!preEnabled" @change="e => preTime = e.detail.value">
            <view :class="['time-box', !preEnabled && 'time-off']">{{ preTime }} ▾</view>
          </picker>
        </view>

        <view class="row">
          <view class="row-left">
            <switch :checked="postEnabled" color="#4f6ef7" @change="e => postEnabled = e.detail.value" />
            <text class="row-label">盘后</text>
          </view>
          <picker mode="time" :value="postTime" :disabled="!postEnabled" @change="e => postTime = e.detail.value">
            <view :class="['time-box', !postEnabled && 'time-off']">{{ postTime }} ▾</view>
          </picker>
        </view>
      </view>

      <!-- LLM 模型 -->
      <view class="card sec">
        <text class="card-title">🤖 LLM 模型</text>
        <text class="hint">用于分析的大模型。只列出已配 API Key 的来源——选了没配 key 的会分析失败白跑。</text>

        <view v-if="providers.length === 0" class="empty">
          未检测到已配 key 的 provider。请在 config/apikeys.local.json 填好后重启服务。
        </view>

        <template v-else>
          <view class="field">
            <text class="label">来源 Provider</text>
            <picker :range="providerNames" @change="onProviderChange">
              <view class="picker-row">
                <text :class="['picker-val', !provider && 'placeholder']">{{ provider || '选择 provider' }}</text>
                <text class="picker-arrow">▾</text>
              </view>
            </picker>
          </view>

          <view class="field">
            <text class="label">深度思考模型（deep think）</text>
            <input class="inp" v-model="deepThink" placeholder="如 deepseek-chat" />
          </view>

          <view class="field">
            <text class="label">快速思考模型（quick think）</text>
            <input class="inp" v-model="quickThink" placeholder="如 deepseek-chat" />
          </view>
        </template>
      </view>

      <button class="btn-primary save-btn" :disabled="saving || loading" @click="save">
        {{ saving ? '保存中...' : '保存设置' }}
      </button>
    </view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '@/utils/api.js'

const loading = ref(true)
const saving = ref(false)

const preEnabled = ref(true)
const preTime = ref('08:30')
const postEnabled = ref(true)
const postTime = ref('15:10')

const providers = ref([])              // [{ provider, deepThinkModel, quickThinkModel }]
const provider = ref('')
const deepThink = ref('')
const quickThink = ref('')

const providerNames = computed(() => providers.value.map(p => p.provider))

function onProviderChange(e) {
  const p = providers.value[e.detail.value]
  if (!p) return
  provider.value = p.provider
  // 切换 provider 时用该源的默认模型预填（用户可再改）
  deepThink.value = p.deepThinkModel || ''
  quickThink.value = p.quickThinkModel || ''
}

async function load() {
  loading.value = true
  try {
    const [s, provs] = await Promise.all([api.getSettings(), api.getProviders()])
    providers.value = provs || []
    if (s) {
      preEnabled.value = s.preMarketEnabled
      preTime.value = s.preMarketTime || '08:30'
      postEnabled.value = s.postMarketEnabled
      postTime.value = s.postMarketTime || '15:10'
      provider.value = s.llmProvider || ''
      deepThink.value = s.deepThinkLlm || ''
      quickThink.value = s.quickThinkLlm || ''
    }
  } catch (e) {
    uni.showToast({ title: '加载失败：' + (e.message || e).slice(0, 40), icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    await api.updateSettings({
      preMarketEnabled: preEnabled.value,
      preMarketTime: preTime.value,
      postMarketEnabled: postEnabled.value,
      postMarketTime: postTime.value,
      llmProvider: provider.value || null,
      deepThinkLlm: deepThink.value || null,
      quickThinkLlm: quickThink.value || null,
    })
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: '保存失败：' + (e.message || e).slice(0, 40), icon: 'none' })
  } finally {
    saving.value = false
  }
}

onLoad(() => load())
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; }
.body { padding: 24rpx; }

.sec { padding: 32rpx; margin-bottom: 24rpx; }
.card-title { display: block; font-size: 32rpx; font-weight: 700; color: $text; }
.hint { display: block; font-size: 24rpx; color: $text-3; margin: 12rpx 0 24rpx; line-height: 1.5; }

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 0;
}
.row-left { display: flex; align-items: center; gap: 16rpx; }
.row-label { font-size: 28rpx; color: $text; font-weight: 600; }
.time-box {
  background: $surface-2;
  border-radius: $radius-sm;
  padding: 16rpx 28rpx;
  font-size: 30rpx;
  color: $text;
  min-width: 140rpx;
  text-align: center;
}
.time-off { color: $text-3; }

.field { margin-bottom: 22rpx; }
.label { display: block; font-size: 24rpx; color: $text-3; margin-bottom: 10rpx; }
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
.inp {
  background: $surface-2;
  border-radius: $radius-sm;
  padding: 22rpx 24rpx;
  font-size: 28rpx;
  color: $text;
}
.empty { font-size: 26rpx; color: $text-3; padding: 16rpx 0; line-height: 1.6; }

.save-btn { width: 100%; padding: 26rpx; font-size: 30rpx; margin-top: 8rpx; }
</style>
