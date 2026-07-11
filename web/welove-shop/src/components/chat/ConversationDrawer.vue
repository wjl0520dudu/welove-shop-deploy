<template>
  <view v-if="visible" class="drawer-root">
    <view class="mask" @tap="$emit('close')"></view>
    <view class="panel">
      <view class="panel-head">
        <text class="panel-title">我的会话</text>
        <view class="new-btn" @tap="$emit('new')">
          <uni-icons type="plusempty" size="16" color="#ffffff" />
          <text>新对话</text>
        </view>
      </view>

      <scroll-view scroll-y class="conv-list">
        <view v-if="loading" class="hint">加载中…</view>
        <view v-else-if="!sorted.length" class="hint">还没有会话，开始新对话吧</view>
        <view
          v-for="conv in sorted"
          :key="conv.id"
          class="conv-item"
          :class="{ active: String(conv.id) === String(currentId) }"
          @tap="$emit('select', conv)"
        >
          <uni-icons
            :type="conv.isPinned ? 'star-filled' : 'chatbubble'"
            size="16"
            :color="conv.isPinned ? '#f97316' : '#14b8a6'"
          />
          <text class="conv-title">{{ conv.title || '新对话' }}</text>
          <view class="more" @tap.stop="openMenu(conv)">
            <uni-icons type="more-filled" size="16" color="#98a2b3" />
          </view>
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'ConversationDrawer',
  props: {
    visible: { type: Boolean, default: false },
    conversations: { type: Array, default: () => [] },
    currentId: { type: [String, Number], default: '' },
    loading: { type: Boolean, default: false }
  },
  emits: ['close', 'new', 'select', 'rename', 'pin', 'delete'],
  computed: {
    sorted() {
      // 置顶优先，其余保持后端返回顺序
      const list = [...(this.conversations || [])]
      return list.sort((a, b) => (b.isPinned ? 1 : 0) - (a.isPinned ? 1 : 0))
    }
  },
  methods: {
    openMenu(conv) {
      const pinLabel = conv.isPinned ? '取消置顶' : '置顶'
      uni.showActionSheet({
        itemList: [pinLabel, '重命名', '删除'],
        success: (res) => {
          if (res.tapIndex === 0) this.$emit('pin', conv)
          else if (res.tapIndex === 1) this.$emit('rename', conv)
          else if (res.tapIndex === 2) this.$emit('delete', conv)
        }
      })
    }
  }
}
</script>

<style scoped>
.drawer-root {
  position: fixed;
  inset: 0;
  z-index: 60;
}
.mask {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.42);
  animation: fade-in 0.2s ease;
}
.panel {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  width: 78%;
  max-width: 560rpx;
  padding: 0 0 env(safe-area-inset-bottom);
  background: #f7faf9;
  box-shadow: 12rpx 0 40rpx rgba(15, 23, 42, 0.16);
  animation: slide-in 0.26s cubic-bezier(0.22, 1, 0.36, 1);
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(28rpx + env(safe-area-inset-top)) 26rpx 22rpx;
}
.panel-title {
  color: #1f2937;
  font-size: 32rpx;
  font-weight: 800;
}
.new-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 12rpx 22rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 700;
}
.conv-list {
  flex: 1;
  padding: 6rpx 18rpx 24rpx;
}
.hint {
  padding: 60rpx 20rpx;
  color: #98a2b3;
  font-size: 25rpx;
  text-align: center;
}
.conv-item {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 12rpx;
  padding: 22rpx 20rpx;
  border-radius: 18rpx;
  background: #ffffff;
  box-shadow: 0 6rpx 16rpx rgba(15, 118, 110, 0.05);
}
.conv-item.active {
  background: #ecfdf9;
  box-shadow: 0 6rpx 18rpx rgba(20, 184, 166, 0.18);
}
.conv-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: #344054;
  font-size: 27rpx;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.more {
  padding: 6rpx;
}
@keyframes slide-in {
  from { transform: translateX(-100%); }
  to { transform: translateX(0); }
}
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
