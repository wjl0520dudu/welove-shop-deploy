<template>
  <view class="empty fade-in-up">
    <view class="empty-icon">
      <uni-icons :type="icon" size="40" color="#c4cdd5" />
    </view>
    <text class="empty-title">{{ title }}</text>
    <text v-if="description" class="empty-desc">{{ description }}</text>
    <slot></slot>
  </view>
</template>

<script>
export default {
  name: 'EmptyState',
  props: {
    title: { type: String, default: '暂无数据' },
    description: { type: String, default: '' },
    icon: { type: String, default: 'info' }
  }
}
</script>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 90rpx 32rpx;
  text-align: center;
}
.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 128rpx;
  height: 128rpx;
  margin-bottom: 24rpx;
  border-radius: 50%;
  background: #f1f5f6;
}
.empty-title {
  display: block;
  font-size: 30rpx;
  font-weight: 700;
  color: #344054;
}
.empty-desc {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #98a2b3;
}
</style>
