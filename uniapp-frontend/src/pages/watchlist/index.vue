<template>
  <view class="container">
    <view class="card add-card">
      <text class="card-title">添加自选股</text>
      <input
        v-model="newTicker"
        class="input"
        placeholder="代码（如 AAPL / 600519.SS / 0700.HK）"
        @confirm="handleAdd"
      />
      <input
        v-model="newName"
        class="input"
        placeholder="名称（可选）"
        @confirm="handleAdd"
      />
      <button class="btn-primary add-btn" :disabled="!newTicker.trim()" @click="handleAdd">
        添加
      </button>
    </view>

    <view v-if="store.loading" class="placeholder">加载中...</view>
    <view v-else-if="store.error" class="placeholder err">{{ store.error }}</view>
    <view v-else-if="store.items.length === 0" class="placeholder">暂无自选股，请先添加</view>

    <view v-else class="list">
      <view v-for="item in store.items" :key="item.ticker" class="card row-item">
        <view class="row-info">
          <text class="ticker">{{ item.ticker }}</text>
          <text class="name">{{ item.name || '—' }}</text>
        </view>
        <view class="row-actions">
          <button class="mini-btn analyze" @click="handleAnalyze(item.ticker)">分析</button>
          <button class="mini-btn danger" @click="handleRemove(item.ticker)">删除</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useWatchlistStore } from '@/store/watchlist.js'
import { api } from '@/utils/api.js'

const store = useWatchlistStore()
const newTicker = ref('')
const newName = ref('')

async function handleAdd() {
  const t = newTicker.value.trim()
  if (!t) return
  try {
    await store.add(t, newName.value.trim() || null)
    newTicker.value = ''
    newName.value = ''
    uni.showToast({ title: '已添加', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: '添加失败：' + (e.message || e).slice(0, 60), icon: 'none' })
  }
}

async function handleRemove(ticker) {
  uni.showModal({
    title: '确认删除',
    content: `从自选股移除 ${ticker} ?`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        await store.remove(ticker)
        uni.showToast({ title: '已删除', icon: 'success' })
      } catch (e) {
        uni.showToast({ title: '删除失败', icon: 'none' })
      }
    },
  })
}

async function handleAnalyze(ticker) {
  try {
    const r = await api.triggerAnalysis(ticker, todayStr())
    uni.navigateTo({ url: `/pages/analysis/index?jobId=${r.jobId}&ticker=${ticker}` })
  } catch (e) {
    uni.showToast({ title: '触发失败：' + (e.message || e).slice(0, 60), icon: 'none' })
  }
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => store.fetch())
</script>

<style lang="scss" scoped>
.container { padding: 24rpx; }

.add-card { padding: 32rpx; margin-bottom: 24rpx; }
.card-title {
  display: block;
  font-size: 32rpx;
  font-weight: 700;
  color: $text;
  margin-bottom: 24rpx;
}
.input {
  width: 100%;
  padding: 22rpx 24rpx;
  border: none;
  border-radius: $radius-sm;
  font-size: 28rpx;
  background: $surface-2;
  margin-bottom: 18rpx;
}
.add-btn { width: 100%; padding: 24rpx; font-size: 30rpx; margin-top: 6rpx; }

.list { display: flex; flex-direction: column; gap: 16rpx; }
.row-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28rpx 32rpx;
}
.row-info { display: flex; flex-direction: column; }
.ticker { font-size: 32rpx; font-weight: 700; color: $text; letter-spacing: 1rpx; }
.name { font-size: 24rpx; color: $text-3; margin-top: 6rpx; }
.row-actions { display: flex; gap: 16rpx; }

.mini-btn {
  font-size: 26rpx;
  padding: 12rpx 28rpx;
  border-radius: $radius-pill;
  line-height: 1.4;
  margin: 0;
}
.mini-btn::after { border: none; }
.analyze { background: rgba(79, 110, 247, 0.1); color: $primary; }
.danger { background: $sell-bg; color: $sell; }

.placeholder {
  text-align: center;
  color: $text-3;
  padding: 100rpx 0;
  font-size: 28rpx;
}
.placeholder.err { color: $sell; }
</style>
