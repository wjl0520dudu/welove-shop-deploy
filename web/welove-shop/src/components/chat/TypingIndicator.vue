<template>
  <view class="typing">
    <view class="dot"></view>
    <view class="dot"></view>
    <view class="dot"></view>
  </view>
</template>

<script>
export default {
  name: 'TypingIndicator'
}
</script>

<style scoped>
.typing {
  display: flex;
  align-items: center;
  gap: 10rpx;
  padding: 6rpx 4rpx;
}
.dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: #14b8a6;
  opacity: 0.4;
  animation: typing-bounce 1.2s infinite ease-in-out;
}
.dot:nth-child(2) { animation-delay: 0.16s; }
.dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes typing-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
  40% { transform: translateY(-8rpx); opacity: 1; }
}
</style>
