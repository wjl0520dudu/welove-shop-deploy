<template>
  <view class="recommend">
    <view class="hero">
      <view class="hero-avatar">AI</view>
      <text class="hero-title">{{ greeting }}</text>
      <text class="hero-sub">描述预算、品类、使用场景或偏好，我来帮你缩小选择范围</text>
    </view>
    <view class="chip-title">
      <uni-icons type="star-filled" size="14" color="#f97316" />
      <text>猜你想问</text>
    </view>
    <view class="chips">
      <view
        v-for="(q, index) in questions"
        :key="index"
        class="chip"
        @tap="$emit('pick', q)"
      >
        <text>{{ q }}</text>
        <uni-icons type="right" size="13" color="#14b8a6" />
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'RecommendChips',
  props: {
    greeting: { type: String, default: '你好，我是你的专属导购助手' },
    questions: { type: Array, default: () => [] }
  },
  emits: ['pick']
}
</script>

<style scoped>
.recommend {
  padding: 20rpx 8rpx;
}
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 20rpx 24rpx 32rpx;
}
.hero-avatar {
  width: 108rpx;
  height: 108rpx;
  border-radius: 50%;
  margin-bottom: 20rpx;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #ffffff;
  font-size: 40rpx;
  font-weight: 800;
  line-height: 108rpx;
  text-align: center;
  box-shadow: 0 16rpx 32rpx rgba(20, 184, 166, 0.28);
}
.hero-title {
  color: #1f2937;
  font-size: 34rpx;
  font-weight: 800;
}
.hero-sub {
  max-width: 520rpx;
  margin-top: 12rpx;
  color: #667085;
  font-size: 24rpx;
  line-height: 1.5;
}
.chip-title {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin: 8rpx 12rpx 16rpx;
  color: #98a2b3;
  font-size: 24rpx;
  font-weight: 700;
}
.chips {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  padding: 0 8rpx;
}
.chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
  padding: 24rpx 26rpx;
  border: 1rpx solid rgba(20, 184, 166, 0.16);
  border-radius: 20rpx;
  background: #ffffff;
  color: #344054;
  font-size: 26rpx;
  box-shadow: 0 8rpx 20rpx rgba(15, 118, 110, 0.05);
}
.chip text {
  flex: 1;
}
</style>
