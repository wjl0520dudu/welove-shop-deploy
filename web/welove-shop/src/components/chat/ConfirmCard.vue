<template>
  <view class="confirm-card">
    <view class="head">
      <uni-icons type="help" size="18" color="#f97316" />
      <text class="q">{{ question }}</text>
    </view>
    <text v-if="desc" class="desc">{{ desc }}</text>
    <view class="actions">
      <view class="btn ghost" @tap="$emit('cancel', card)">{{ cancelText }}</view>
      <view class="btn primary" @tap="$emit('confirm', card)">{{ confirmText }}</view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ConfirmCard',
  props: {
    card: { type: Object, default: () => ({}) }
  },
  emits: ['confirm', 'cancel'],
  computed: {
    question() {
      return this.card.question || this.card.title || this.card.text || '是否继续该操作？'
    },
    desc() {
      return this.card.desc || this.card.description || ''
    },
    confirmText() {
      return this.card.confirmText || this.card.okText || '确认'
    },
    cancelText() {
      return this.card.cancelText || '再想想'
    }
  }
}
</script>

<style scoped>
.confirm-card {
  padding: 22rpx 24rpx;
  border: 1rpx solid rgba(249, 115, 22, 0.24);
  border-radius: 20rpx;
  background: #fffaf5;
}
.head {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.q {
  color: #1f2937;
  font-size: 27rpx;
  font-weight: 700;
  line-height: 1.4;
}
.desc {
  display: block;
  margin-top: 8rpx;
  color: #667085;
  font-size: 24rpx;
  line-height: 1.5;
}
.actions {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
}
.btn {
  flex: 1;
  height: 72rpx;
  border-radius: 999rpx;
  font-size: 26rpx;
  font-weight: 700;
  text-align: center;
  line-height: 72rpx;
}
.ghost {
  background: #ffffff;
  border: 1rpx solid #e5e7eb;
  color: #667085;
}
.primary {
  background: linear-gradient(135deg, #f97316, #fb923c);
  color: #ffffff;
}
</style>
