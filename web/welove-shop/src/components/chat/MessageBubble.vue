<template>
  <view class="row" :class="isUser ? 'user-row' : 'assistant-row'">
    <view v-if="!isUser" class="avatar ai">AI</view>
    <view class="bubble-wrap">
      <view
        class="bubble"
        :class="isUser ? 'user' : 'assistant'"
        @longpress="$emit('longpress', message)"
      >
        <TypingIndicator v-if="showTyping" />
        <template v-else>
          <text class="text" :user-select="true" :selectable="true">{{ message.content }}</text><text v-if="message.streaming" class="cursor">▍</text>
        </template>
      </view>
      <view v-if="message.errored" class="errored">
        <uni-icons type="info" size="13" color="#e17055" />
        <text>回复中断</text>
        <text class="retry" @tap="$emit('retry', message)">重试</text>
      </view>
      <view v-else-if="feedbackLabel" class="feedback-tag">
        <uni-icons :type="message.feedbackType === 'like' ? 'hand-up-filled' : 'hand-down-filled'" size="12" color="#98a2b3" />
        <text>{{ feedbackLabel }}</text>
      </view>
    </view>
    <view v-if="isUser" class="avatar user">{{ userInitial }}</view>
  </view>
</template>

<script>
import TypingIndicator from './TypingIndicator.vue'

export default {
  name: 'MessageBubble',
  components: { TypingIndicator },
  props: {
    message: { type: Object, required: true },
    userInitial: { type: String, default: '我' }
  },
  emits: ['longpress', 'retry'],
  computed: {
    isUser() {
      return this.message.role === 'user'
    },
    showTyping() {
      return !this.isUser && this.message.pending && !this.message.content
    },
    feedbackLabel() {
      if (this.message.feedbackType === 'like') return '已赞'
      if (this.message.feedbackType === 'dislike') return '已踩'
      return ''
    }
  }
}
</script>

<style scoped>
.row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  margin-bottom: 26rpx;
}
.user-row { flex-direction: row; justify-content: flex-end; }
.assistant-row { justify-content: flex-start; }
.avatar {
  flex-shrink: 0;
  width: 62rpx;
  height: 62rpx;
  border-radius: 50%;
  font-size: 24rpx;
  font-weight: 800;
  line-height: 62rpx;
  text-align: center;
}
.avatar.ai {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #ffffff;
}
.avatar.user {
  background: #fff1e6;
  color: #f97316;
}
.bubble-wrap {
  max-width: 78%;
  display: flex;
  flex-direction: column;
}
.assistant-row .bubble-wrap { align-items: flex-start; }
.user-row .bubble-wrap { align-items: flex-end; }
.bubble {
  padding: 22rpx 24rpx;
  border-radius: 22rpx;
  font-size: 28rpx;
  line-height: 1.6;
  word-break: break-word;
}
.assistant {
  background: #ffffff;
  color: #344054;
  border-top-left-radius: 6rpx;
  box-shadow: 0 10rpx 26rpx rgba(15, 118, 110, 0.08);
}
.user {
  background: linear-gradient(135deg, #14b8a6, #0f9488);
  color: #ffffff;
  border-top-right-radius: 6rpx;
}
.text {
  white-space: pre-wrap;
}
.cursor {
  color: #14b8a6;
  font-weight: 700;
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.errored {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-top: 10rpx;
  color: #e17055;
  font-size: 22rpx;
}
.retry {
  margin-left: 6rpx;
  color: #14b8a6;
  font-weight: 700;
}
.feedback-tag {
  display: flex;
  align-items: center;
  gap: 6rpx;
  margin-top: 10rpx;
  color: #98a2b3;
  font-size: 21rpx;
}
</style>
