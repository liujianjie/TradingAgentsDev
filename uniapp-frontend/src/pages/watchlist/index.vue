<template>
  <view class="container">
    <view class="add-card">
      <view class="row">
        <input
          v-model="newTicker"
          class="input"
          placeholder="股票代码（如 AAPL / 600519.SS / 0700.HK）"
          @confirm="handleAdd"
        />
      </view>
      <view class="row">
        <input
          v-model="newName"
          class="input"
          placeholder="名称（可选）"
          @confirm="handleAdd"
        />
      </view>
      <button class="btn btn-primary" :disabled="!newTicker.trim()" @click="handleAdd">
        添加
      </button>
    </view>

    <view v-if="store.loading" class="muted">加载中...</view>
    <view v-else-if="store.error" class="error">{{ store.error }}</view>
    <view v-else-if="store.items.length === 0" class="muted">暂无自选股，请先添加</view>

    <view v-else class="list">
      <view
        v-for="item in store.items"
        :key="item.ticker"
        class="row-item"
      >
        <view class="row-info">
          <text class="ticker">{{ item.ticker }}</text>
          <text class="name">{{ item.name || '—' }}</text>
        </view>
        <view class="row-actions">
          <button class="btn btn-small" @click="handleAnalyze(item.ticker)">分析</button>
          <button class="btn btn-small btn-danger" @click="handleRemove(item.ticker)">删除</button>
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
.container {
  padding: 24rpx;
}
.add-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}
.row {
  margin-bottom: 16rpx;
}
.input {
  width: 100%;
  padding: 16rpx;
  border: 1rpx solid #e0e0e0;
  border-radius: 8rpx;
  font-size: 28rpx;
  background: #fafafa;
}
.btn {
  border: none;
  padding: 18rpx 32rpx;
  border-radius: 8rpx;
  font-size: 28rpx;
  background: #f0f0f0;
}
.btn-primary {
  background: #1976d2;
  color: #fff;
}
.btn-primary[disabled] {
  background: #b0bec5;
}
.btn-small {
  font-size: 24rpx;
  padding: 8rpx 20rpx;
  margin-left: 12rpx;
}
.btn-danger {
  background: #fee;
  color: #c62828;
}
.list {
  background: #fff;
  border-radius: 16rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.05);
}
.row-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.row-item:last-child {
  border-bottom: none;
}
.row-info {
  display: flex;
  flex-direction: column;
}
.ticker {
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
}
.name {
  font-size: 24rpx;
  color: #999;
  margin-top: 4rpx;
}
.row-actions {
  display: flex;
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
