<template>
  <view class="card guide-card">
    <text class="section-title">指标怎么读</text>
    <text class="guide-intro">先看“杠杆成交比”，再用其他数据判断成交来自哪里。</text>

    <view class="tip-list">
      <view class="tip-item">
        <text class="tip-index">1</text>
        <view>
          <text class="tip-title">杠杆成交比</text>
          <text class="tip-copy">
            杠杆产品实际成交额 ÷ 正股成交额。0.30 表示每 $1 正股成交，对应约 $0.30 杠杆产品成交。
          </text>
        </view>
      </view>
      <view class="tip-item">
        <text class="tip-index">2</text>
        <view>
          <text class="tip-title">杠杆倍数折算比</text>
          <text class="tip-copy">
            把 2 倍产品成交额按 2 倍、3 倍产品按 3 倍折算，用来观察名义杠杆强度。它不是资金净流入。
          </text>
        </view>
      </view>
      <view class="tip-item">
        <text class="tip-index">3</text>
        <view>
          <text class="tip-title">正向与反向成交</text>
          <text class="tip-copy">
            正向产品押注上涨，反向产品押注下跌；两者都计入主指标，所以高杠杆成交比不等于市场一致看多。
          </text>
        </view>
      </view>
      <view class="tip-item">
        <text class="tip-index">4</text>
        <view>
          <text class="tip-title">较前日</text>
          <text class="tip-copy">
            是杠杆成交比相对上一有效交易日的绝对变化。例如从 0.30 到 0.35，显示 +0.05，不是上涨 5%。
          </text>
        </view>
      </view>
    </view>

    <view class="example-box">
      <text class="example-label">一个简单算例</text>
      <text class="example-copy">正股成交 $100，2倍正向产品成交 $20，-2倍反向产品成交 $10：</text>
      <text class="example-result">杠杆成交比 = (20 + 10) ÷ 100 = 0.30</text>
      <text class="example-result">杠杆倍数折算比 = (20×2 + 10×2) ÷ 100 = 0.60</text>
    </view>

    <view class="warning-box">
      <text class="warning-title">重要提醒</text>
      <text class="warning-copy">
        这里统计的是成交额，不是持仓、融资余额或公司财务杠杆。同一份产品可以在一天内反复换手，因此比率可以接近或超过 1。
      </text>
    </view>

    <view class="method-block">
      <text class="method-title">计算与数据</text>
      <text class="method-copy">
        成交额按未复权收盘价 × 成交量计算，再按当日汇率统一为美元；产品清单为人工维护的 best-effort 覆盖。
      </text>
      <view class="method-meta">
        <text>数据：{{ methodology?.data_source || '—' }}</text>
        <text>清单版本：{{ methodology?.registry_version || '—' }}</text>
      </view>
    </view>

    <text class="disclaimer">仅供研究，不构成投资建议。免费行情可能存在延迟、复权差异或缺失。</text>
  </view>
</template>

<script setup>
defineProps({
  methodology: { type: Object, default: null },
})
</script>

<style lang="scss" scoped>
.guide-card { padding: 30rpx; margin-top: 24rpx; }
.section-title { display: block; color: $text; font-size: 31rpx; font-weight: 800; }
.guide-intro { display: block; margin-top: 8rpx; color: $text-3; font-size: 22rpx; line-height: 1.55; }
.tip-list { margin-top: 24rpx; }
.tip-item { display: grid; grid-template-columns: 46rpx minmax(0, 1fr); gap: 16rpx; }
.tip-item + .tip-item { margin-top: 22rpx; padding-top: 22rpx; border-top: 1rpx solid $line; }
.tip-index {
  width: 42rpx;
  height: 42rpx;
  border-radius: 50%;
  background: rgba(79, 110, 247, .11);
  color: $primary;
  font-size: 21rpx;
  font-weight: 800;
  line-height: 42rpx;
  text-align: center;
}
.tip-title, .tip-copy { display: block; }
.tip-title { color: $text; font-size: 24rpx; font-weight: 800; }
.tip-copy { margin-top: 6rpx; color: $text-2; font-size: 21rpx; line-height: 1.7; }
.example-box { margin-top: 26rpx; padding: 24rpx; border-radius: $radius-sm; background: #f3f6ff; }
.example-label, .example-copy, .example-result { display: block; }
.example-label { color: $primary; font-size: 22rpx; font-weight: 800; }
.example-copy { margin-top: 10rpx; color: $text-2; font-size: 21rpx; line-height: 1.6; }
.example-result { margin-top: 8rpx; color: $text; font-size: 21rpx; font-weight: 700; line-height: 1.55; }
.warning-box { margin-top: 18rpx; padding: 22rpx 24rpx; border-left: 6rpx solid #e09b43; background: #fffaf0; }
.warning-title, .warning-copy { display: block; }
.warning-title { color: #87550e; font-size: 22rpx; font-weight: 800; }
.warning-copy { margin-top: 6rpx; color: #8f672d; font-size: 20rpx; line-height: 1.65; }
.method-block { margin-top: 26rpx; padding-top: 24rpx; border-top: 1rpx solid $line; }
.method-title { display: block; color: $text; font-size: 24rpx; font-weight: 800; }
.method-copy { display: block; margin-top: 8rpx; color: $text-2; font-size: 21rpx; line-height: 1.7; }
.method-meta { display: flex; flex-direction: column; gap: 5rpx; margin-top: 16rpx; color: $text-3; font-size: 20rpx; }
.disclaimer { display: block; margin-top: 20rpx; padding-top: 18rpx; border-top: 1rpx solid $line; color: $text-3; font-size: 19rpx; line-height: 1.55; }

@media (min-width: 768px) {
  .tip-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }
  .tip-item + .tip-item { margin-top: 0; padding-top: 0; border-top: 0; }
}
</style>
