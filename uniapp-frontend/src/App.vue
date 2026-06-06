<script setup>
import { onLaunch } from '@dcloudio/uni-app'

onLaunch(() => {
  console.log('TradingAgents 启动')
})
</script>

<style lang="scss">
/* ===== 全局基础（清新金融卡片风）===== */
page {
  background-color: $bg;
  color: $text;
  font-family: -apple-system, "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif;
  font-size: 28rpx;
  line-height: 1.5;
}

/* 卡片 */
.card {
  background: $surface;
  border-radius: $radius;
  box-shadow: $shadow;
}

/* 渐变头 */
.grad-header {
  background: linear-gradient(135deg, $grad-start, $grad-end);
  border-radius: 0 0 $radius $radius;
  color: #fff;
}

/* 交易信号胶囊 */
.pill {
  display: inline-flex;
  align-items: center;
  padding: 6rpx 22rpx;
  border-radius: $radius-pill;
  font-size: 24rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}
.pill-buy  { background: $buy-bg;  color: $buy; }
.pill-sell { background: $sell-bg; color: $sell; }
.pill-hold { background: $hold-bg; color: $hold; }
.pill-muted { background: $surface-2; color: $text-3; }

/* 主按钮 */
.btn-primary {
  background: linear-gradient(135deg, $grad-start, $grad-end);
  color: #fff;
  border: none;
  border-radius: $radius-sm;
  font-weight: 600;
  box-shadow: 0 6rpx 16rpx rgba(79, 110, 247, 0.28);
}
.btn-primary[disabled] {
  background: #c3cbe6;
  box-shadow: none;
}

/* 次级/幽灵按钮 */
.btn-ghost {
  background: $surface;
  color: $primary;
  border: 1rpx solid rgba(79, 110, 247, 0.25);
  border-radius: $radius-sm;
  font-weight: 600;
}
</style>
