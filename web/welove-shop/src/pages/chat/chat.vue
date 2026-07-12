<template>
  <view class="page chat-page">
    <view class="topbar">
      <view class="icon-btn" @tap="openDrawer">
        <uni-icons type="bars" size="22" color="#0f766e" />
      </view>
      <view class="title-wrap">
        <text class="title">{{ headerTitle }}</text>
      </view>
      <view class="icon-btn" @tap="newChat">
        <uni-icons type="plusempty" size="22" color="#0f766e" />
      </view>
    </view>

    <scroll-view
      class="messages"
      scroll-y
      :scroll-into-view="scrollIntoId"
      :scroll-with-animation="true"
    >
      <RecommendChips
        v-if="isEmpty"
        :greeting="greeting"
        :questions="recommended"
        @pick="pickRecommend"
      />
      <template v-else>
        <view v-for="msg in messages" :key="msg._localId" class="msg-block">
          <MessageBubble
            :message="msg"
            :user-initial="userInitial"
            @longpress="onMessageLongpress"
            @retry="retryMessage"
          />
          <view v-if="msg.role === 'assistant'" class="cards-under">
            <ChatProductCards
              v-if="msg.productCards && msg.productCards.length"
              :products="msg.productCards"
              @open="onProductOpen"
              @add="onProductAdd"
            />
            <ConfirmCard
              v-if="msg.confirmCard"
              :card="msg.confirmCard"
              @confirm="onConfirmCard"
              @cancel="onCancelCard"
            />
            <CartSelectionCard
              v-if="msg.cartSelection"
              :card="msg.cartSelection"
              @submit="onCartSelectionSubmit"
            />
          </view>
        </view>
        <view id="msg-bottom" class="bottom-anchor"></view>
      </template>
    </scroll-view>

    <view class="input-bar">
      <view class="input-wrap">
        <input
          v-model="input"
          class="chat-input"
          placeholder="输入你的购物需求"
          confirm-type="send"
          :adjust-position="false"
          @confirm="onSend"
        />
      </view>
      <view v-if="!streaming" class="send-btn" :class="{ disabled: !input.trim() }" @tap="onSend">
        <uni-icons type="paperplane-filled" size="22" color="#ffffff" />
      </view>
      <view v-else class="stop-btn" @tap="stop">
        <view class="stop-square"></view>
      </view>
    </view>

    <ConversationDrawer
      :visible="drawerVisible"
      :conversations="conversations"
      :current-id="currentConversation ? currentConversation.id : ''"
      :loading="loadingConversations"
      @close="closeDrawer"
      @new="newChat"
      @select="selectConversation"
      @rename="renameConversation"
      @pin="pinConversation"
      @delete="onDeleteConversation"
    />

    <ProductSkuSheet
      :visible="showSkuSheet"
      :skus="skuList"
      @close="showSkuSheet = false"
      @confirm="onSkuConfirm"
    />
  </view>
</template>

<script>
import { requireLoginFromProtectedTab, toLogin } from '../../utils/routeGuard'
import { supportsEventStream } from '../../utils/sse'
import { refreshAccessToken } from '../../utils/request'
import { buildRecommendedQuestions } from '../../utils/chatRecommend'
import {
  streamMessage,
  sendMessage,
  getMessages,
  feedback as feedbackApi,
  stopStream,
  updateConversation as updateConversationApi,
  deleteConversation as deleteConversationApi
} from '../../api/chat'
import { getProductSkus } from '../../api/product'
import { addCart } from '../../api/cart'
import userStore from '../../store/user'
import cartStore from '../../store/cart'
import chatStore from '../../store/chat'

import MessageBubble from '../../components/chat/MessageBubble.vue'
import ChatProductCards from '../../components/chat/ChatProductCards.vue'
import ConfirmCard from '../../components/chat/ConfirmCard.vue'
import CartSelectionCard from '../../components/chat/CartSelectionCard.vue'
import ConversationDrawer from '../../components/chat/ConversationDrawer.vue'
import RecommendChips from '../../components/chat/RecommendChips.vue'
import ProductSkuSheet from '../../components/ProductSkuSheet.vue'

export default {
  components: {
    MessageBubble,
    ChatProductCards,
    ConfirmCard,
    CartSelectionCard,
    ConversationDrawer,
    RecommendChips,
    ProductSkuSheet
  },
  data() {
    return {
      input: '',
      messages: [],
      conversations: [],
      currentConversation: null,
      streaming: false,
      loadingConversations: false,
      drawerVisible: false,
      showSkuSheet: false,
      skuList: [],
      pendingCartProductId: null,
      recommended: [],
      scrollIntoId: '',
      /** 记录当前正在 SSE 流的会话 ID，用于切换窗口后其他会话收到消息时标红点 */
      _streamingConvId: null
    }
  },
  computed: {
    isEmpty() {
      return !this.messages.length
    },
    headerTitle() {
      return (this.currentConversation && this.currentConversation.title) || 'AI 导购'
    },
    userInitial() {
      const name = userStore.state.user && userStore.state.user.username
      return name ? String(name).charAt(0).toUpperCase() : '我'
    },
    greeting() {
      const name = userStore.state.user && userStore.state.user.username
      return name ? `你好 ${name}，我是你的专属导购助手` : '你好，我是你的专属导购助手'
    }
  },
  onShow() {
    if (!requireLoginFromProtectedTab('/pages/chat/chat')) return
    userStore.restore()
    this.buildRecommended()
    if (chatStore.state.streaming) return
    // 快照会话内存缓存到响应式副本
    this.messages = chatStore.state.messages
    chatStore.setMessages(this.messages)
    this.conversations = [...chatStore.state.conversations]
    this.currentConversation = chatStore.state.currentConversation
    if (!this.conversations.length) {
      this.loadConversations()
    }
    this.scrollToBottom()
  },
  onHide() {
    // 不再在 onHide 中 abort——切换窗口时 SSE 应在后台继续接收，
    // 与豆包行为一致。只有真正离开页面（onUnload）才断开连接。
  },
  onUnload() {
    this.abortStream()
  },
  methods: {
    /* ---------- 会话列表 ---------- */
    async loadConversations() {
      this.loadingConversations = true
      try {
        const list = await chatStore.loadConversations()
        this.conversations = [...list]
      } catch (e) {
        // 静默失败，空态兜底
      } finally {
        this.loadingConversations = false
      }
    },
    openDrawer() {
      this.drawerVisible = true
      if (!this.conversations.length) this.loadConversations()
    },
    closeDrawer() {
      this.drawerVisible = false
    },
    async selectConversation(conv) {
      this.closeDrawer()
      if (this.streaming) this.stop()
      chatStore.clearNewMessage(conv.id)
      try {
        await chatStore.openConversation(conv)
        this.currentConversation = conv
        this.messages = (chatStore.state.messages || []).map((m) => this.hydrateServerMessage(m))
        chatStore.setMessages(this.messages)
        this.scrollToBottom()
      } catch (e) {
        uni.showToast({ title: '加载会话失败', icon: 'none' })
      }
    },
    newChat() {
      if (this.streaming) this.stop()
      this.currentConversation = null
      this.messages = []
      chatStore.setCurrentConversation(null)
      chatStore.setMessages(this.messages)
      this.buildRecommended()
      this.closeDrawer()
    },
    renameConversation(conv) {
      uni.showModal({
        title: '重命名会话',
        editable: true,
        placeholderText: conv.title || '新对话',
        success: async (res) => {
          const title = res.confirm && res.content ? res.content.trim() : ''
          if (!title) return
          try {
            await updateConversationApi(conv.id, { title })
            conv.title = title
            this.conversations = [...this.conversations]
            chatStore.setConversations(this.conversations)
          } catch (e) {
            uni.showToast({ title: '重命名失败', icon: 'none' })
          }
        }
      })
    },
    async pinConversation(conv) {
      const next = conv.isPinned ? 0 : 1
      try {
        await updateConversationApi(conv.id, { isPinned: next })
        conv.isPinned = next
        this.conversations = [...this.conversations]
        chatStore.setConversations(this.conversations)
      } catch (e) {
        uni.showToast({ title: '操作失败', icon: 'none' })
      }
    },
    onDeleteConversation(conv) {
      uni.showModal({
        title: '删除会话',
        content: '确定删除该会话吗？删除后不可恢复。',
        success: async (res) => {
          if (!res.confirm) return
          try {
            await deleteConversationApi(conv.id)
            this.conversations = this.conversations.filter((c) => String(c.id) !== String(conv.id))
            chatStore.setConversations(this.conversations)
            if (this.currentConversation && String(this.currentConversation.id) === String(conv.id)) {
              this.newChat()
            }
          } catch (e) {
            uni.showToast({ title: '删除失败', icon: 'none' })
          }
        }
      })
    },

    /* ---------- 发送与流式 ---------- */
    onSend() {
      this.send()
    },
    pickRecommend(question) {
      this.send(question)
    },
    async send(text) {
      const content = (text != null ? text : this.input).trim()
      if (!content) {
        uni.showToast({ title: '请输入内容', icon: 'none' })
        return
      }
      if (this.streaming) return
      this.input = ''

      const userMsg = this.makeMessage({ role: 'user', content })
      this.messages.push(userMsg)
      this.scrollToBottom()

      let conv
      try {
        conv = await chatStore.ensureConversation(this.titleFrom(content))
        this.currentConversation = conv
        this.conversations = [...chatStore.state.conversations]
      } catch (e) {
        uni.showToast({ title: '创建会话失败', icon: 'none' })
        return
      }

      const assistant = this.makeMessage({ role: 'assistant', content: '', pending: true, streaming: true })
      this.messages.push(assistant)
      // Vue3: push 进响应式数组后，须取回数组内的响应式代理再改，
      // 否则改的是裸对象引用，不会触发重渲染（流式 token 收到了但聊天框不刷新）。
      const reactiveAssistant = this.messages[this.messages.length - 1]
      this.setStreaming(true)
      this.scrollToBottom()

      await this.runStream(conv.id, content, reactiveAssistant, true)
    },
    async runStream(conversationId, content, assistant, allowAuthRetry, retry = false) {
      this._streamingConvId = conversationId
      if (!supportsEventStream()) {
        const ok = await this.fallbackSend(conversationId, content, assistant)
        if (!ok) this.markErrored(assistant)
        return
      }

      const payload = this.buildPayload(conversationId, content, retry)
      let gotText = false
      const callbacks = {
        onText: (delta) => {
          if (!delta) return
          assistant.pending = false
          assistant.content += delta
          gotText = true
          this.scrollToBottom()
        },
        onProductCards: (list) => { assistant.productCards = list || []; this.scrollToBottom() },
        onConfirm: (card) => { assistant.confirmCard = card || null; this.scrollToBottom() },
        onCartSelection: (card) => { assistant.cartSelection = card || null; this.scrollToBottom() },
        onRouted: (t) => { assistant.taskType = t || '' },
        // final 兜底：若某类回复没有逐 token 流（如 unknown/error 静态回复），用 final 的完整答案补上
        onFinalText: (text) => {
          if (text && !gotText) {
            assistant.pending = false
            assistant.content = text
            gotText = true
            this.scrollToBottom()
          }
        },
        onDone: (data) => {
          this.finishStream(assistant, data, conversationId)
          // SSE 开始时的会话与当前会话不一致 → 用户已切走到其他窗口/会话
          if (this.currentConversation && String(this.currentConversation.id) !== String(this._streamingConvId)) {
            chatStore.markNewMessage(this._streamingConvId)
          }
        },
        onError: () => {
          // 注意:AbortError 路径不会走这里——chat.vue 已在 runStream 的 catch 里显式 return。
          // 走到 onError 一定是后端真正发了 error 事件(LLM 异常 / ai-service 5xx 等)。
          assistant.pending = false
          assistant.streaming = false
          if (!assistant.content) {
            // 没有任何 token 才标 errored,提示用户「回复中断」
            assistant.errored = true
          }
          this.setStreaming(false)
          if (this.streamHandle) this.streamHandle.abort()
        }
      }

      this.streamHandle = streamMessage(payload, callbacks)
      try {
        await this.streamHandle.promise
        if (assistant.streaming) this.finishStream(assistant, {}, conversationId)
      } catch (err) {
        if (err && err.name === 'AbortError') {
          // 用户主动中止:保留已收 token,标 stopped,主动把半成品发给后端落库。
          // 网络通时由 stopStream 写库;网络断时由后端 Flux.doOnCancel 兜底;SQL 去重避免重复。
          assistant.pending = false
          assistant.streaming = false
          assistant.stopped = true
          assistant.stoppedReason = 'user_abort'
          this.persistStoppedSnapshot(conversationId, assistant)
          this.setStreaming(false)
          return
        }
        if ((err && (err.status === 401 || err.status === 403)) && allowAuthRetry && !gotText) {
          const refreshed = await refreshAccessToken().catch(() => false)
          if (refreshed) {
            return this.runStream(conversationId, content, assistant, false)
          }
          this.setStreaming(false)
          toLogin('/pages/chat/chat')
          return
        }
        if (!gotText) {
          const ok = await this.fallbackSend(conversationId, content, assistant)
          if (ok) return
        }
        this.markErrored(assistant)
      } finally {
        this.streamHandle = null
      }
    },
    async fallbackSend(conversationId, content, assistant) {
      try {
        const user = userStore.state.user || {}
        const msg = await sendMessage({ userId: Number(user.id) || undefined, conversationId, content })
        assistant.pending = false
        assistant.content = (msg && msg.content) || ''
        assistant.id = msg && msg.id
        assistant.productCards = (msg && msg.productCards) || []
        assistant.confirmCard = (msg && msg.confirmCard) || null
        assistant.cartSelection = (msg && msg.cartSelection) || null
        assistant.streaming = false
        this.setStreaming(false)
        this.scrollToBottom()
        return Boolean(assistant.content || assistant.productCards.length)
      } catch (e) {
        return false
      }
    },
    async finishStream(assistant, data, conversationId) {
      assistant.pending = false
      assistant.streaming = false
      if (data && data.messageId) assistant.id = data.messageId
      this.setStreaming(false)
      if (!assistant.id) {
        try {
          const list = await getMessages(conversationId)
          const arr = Array.isArray(list) ? list : (list && list.records) || []
          for (let i = arr.length - 1; i >= 0; i--) {
            if (arr[i].role === 'assistant') { assistant.id = arr[i].id; break }
          }
        } catch (e) {
          // 拿不到 id 时，反馈按钮将不可用，静默即可
        }
      }
    },
    markErrored(assistant) {
      assistant.pending = false
      assistant.streaming = false
      if (!assistant.content) assistant.errored = true
      this.setStreaming(false)
    },
    stop() {
      this.abortStream()
    },
    abortStream() {
      if (this.streamHandle) {
        this.streamHandle.abort()
        this.streamHandle = null
      }
    },
    /**
     * 把当前 assistant 半成品快照发给后端落库(status=truncated)。
     * 仅在前端 AbortError 路径调用;失败也不抛错(后端 doOnCancel 会兜底)。
     */
    persistStoppedSnapshot(conversationId, assistant) {
      if (!conversationId) return
      const payload = {
        conversationId,
        content: assistant.content || '',
        productCards: assistant.productCards && assistant.productCards.length ? assistant.productCards : null,
        confirmCard: assistant.confirmCard || null,
        cartSelection: assistant.cartSelection || null,
        taskType: assistant.taskType || '',
        clientTs: Date.now()
      }
      stopStream(payload)
        .then((messageId) => {
          if (messageId) assistant.id = messageId
        })
        .catch(() => {
          // 静默失败,后端 Flux.doOnCancel 已兜底,UI 不阻塞
        })
    },
    async retryMessage(message) {
      if (this.streaming) return
      // 用 _localId 定位原消息:MessageBubble emit 出来的可能是 chatStore 里的引用,
      // 而 this.messages 在 selectConversation 时被 map(hydrate) 重新创建,引用对比必失败。
      const localId = message && message._localId
      const target = (localId ? this.messages.find((m) => m._localId === localId) : null) || message
      const idx = this.messages.indexOf(target)
      let userContent = ''
      for (let i = idx - 1; i >= 0; i--) {
        if (this.messages[i].role === 'user') { userContent = this.messages[i].content; break }
      }
      if (!userContent) {
        console.warn('[retry] no preceding user message found, abort retry', { localId, idx, msgCount: this.messages.length })
        uni.showToast({ title: '找不到原始问题,无法重发', icon: 'none' })
        return
      }
      const conversationId = this.currentConversation && this.currentConversation.id
      if (!conversationId) {
        console.warn('[retry] no current conversation, abort retry')
        uni.showToast({ title: '会话已失效,请刷新页面', icon: 'none' })
        return
      }
      console.log('[retry] start', { localId, conversationId, userContent: userContent.slice(0, 30) })
      target.errored = false
      target.stopped = false
      target.stoppedReason = ''
      target.pending = true
      target.streaming = true
      target.content = ''
      target.productCards = []
      target.confirmCard = null
      target.cartSelection = null
      target.id = null
      target.taskType = ''
      this.setStreaming(true)
      this.scrollToBottom()
      try {
        await this.runStream(conversationId, userContent, target, true, true)
        console.log('[retry] runStream resolved')
      } catch (e) {
        console.error('[retry] runStream rejected', e)
        // 出错时确保 UI 状态能恢复,避免卡在 streaming=true
        target.streaming = false
        target.pending = false
        this.setStreaming(false)
        uni.showToast({ title: '重发失败,请稍后再试', icon: 'none' })
      }
    },

    /* ---------- 商品卡 / 加购 ---------- */
    onProductOpen(product) {
      const id = product.id || product.productId || product.product_id
      if (id) uni.navigateTo({ url: `/pages/product-detail/product-detail?id=${id}` })
    },
    async onProductAdd(product) {
      const productId = product.id || product.productId || product.product_id
      if (!productId) return
      this.pendingCartProductId = productId
      try {
        const skus = await getProductSkus(productId)
        this.skuList = Array.isArray(skus) ? skus : []
      } catch (e) {
        this.skuList = []
      }
      if (this.skuList.length) {
        this.showSkuSheet = true
      } else {
        this.addToCart(productId, null)
      }
    },
    onSkuConfirm(sku) {
      this.showSkuSheet = false
      this.addToCart(this.pendingCartProductId, sku && sku.id)
    },
    async addToCart(productId, skuId) {
      try {
        await addCart(productId, skuId)
        cartStore.bump(1)
        cartStore.loadCart().catch(() => {})
        uni.showToast({ title: '已加入购物车', icon: 'success' })
      } catch (e) {
        uni.showToast({ title: '加入购物车失败', icon: 'none' })
      }
    },
    async onCartSelectionSubmit(items) {
      if (!items || !items.length) return
      uni.showLoading({ title: '加入中…', mask: true })
      let ok = 0
      for (const it of items) {
        try {
          await addCart(it.productId || it.id, it.skuId || null)
          ok += 1
        } catch (e) {
          // 单件失败不阻断其余
        }
      }
      if (ok) cartStore.bump(ok)
      cartStore.loadCart().catch(() => {})
      uni.hideLoading()
      uni.showToast({ title: ok ? `已加入 ${ok} 件` : '加入失败', icon: ok ? 'success' : 'none' })
    },
    syncBadge(count) {
      return cartStore.syncBadge(count)
    },

    /* ---------- 确认卡 / 反馈 ---------- */
    onConfirmCard(card) {
      this.send(card.confirmValue || card.confirmText || '确认')
    },
    onCancelCard(card) {
      this.send(card.cancelValue || card.cancelText || '再想想')
    },
    onMessageLongpress(message) {
      const items = ['复制']
      const canFeedback = message.role === 'assistant' && message.id
      if (canFeedback) items.push('赞', '踩')
      uni.showActionSheet({
        itemList: items,
        success: (res) => {
          const label = items[res.tapIndex]
          if (label === '复制') {
            uni.setClipboardData({ data: message.content || '', success: () => uni.showToast({ title: '已复制', icon: 'none' }) })
          } else if (label === '赞') {
            this.doFeedback(message, 'like')
          } else if (label === '踩') {
            this.doFeedback(message, 'dislike')
          }
        }
      })
    },
    async doFeedback(message, type) {
      try {
        await feedbackApi(message.id, type)
        message.feedbackType = type
      } catch (e) {
        uni.showToast({ title: '反馈失败', icon: 'none' })
      }
    },

    /* ---------- 工具 ---------- */
    setStreaming(v) {
      this.streaming = v
      chatStore.setStreaming(v)
    },
    buildRecommended() {
      this.recommended = buildRecommendedQuestions(userStore.state.user || {}, { limit: 4 })
    },
    buildPayload(conversationId, content, retry = false) {
      const u = userStore.state.user || {}
      return {
        userId: Number(u.id) || undefined,
        conversationId,
        content,
        username: u.username || 'user',
        isAdmin: false,
        gender: u.gender,
        skinType: u.skinType,
        preferenceTags: this.normalizeTags(u.preferenceTags),
        retry
      }
    },
    normalizeTags(tags) {
      if (!tags) return []
      if (Array.isArray(tags)) return tags.filter(Boolean)
      return String(tags).split(/[,，、\s]+/).filter(Boolean)
    },
    titleFrom(content) {
      const text = String(content).trim()
      return text.length > 16 ? `${text.slice(0, 16)}…` : text
    },
    makeMessage(fields) {
      this._seq = (this._seq || 0) + 1
      return {
        _localId: `l${this._seq}`,
        id: null,
        role: 'assistant',
        content: '',
        productCards: [],
        confirmCard: null,
        cartSelection: null,
        taskType: '',
        feedbackType: '',
        pending: false,
        streaming: false,
        errored: false,
        stopped: false,
        stoppedReason: '',
        ...fields
      }
    },
    hydrateServerMessage(m) {
      // 后端 status='truncated' 在前端映射为 stopped,刷新/切回时仍能看到「已停止」标签
      const isTruncated = m.status === 'truncated'
      return {
        _localId: `s${m.id}`,
        id: m.id,
        conversationId: m.conversationId,
        role: m.role,
        content: m.content || '',
        productCards: m.productCards || [],
        confirmCard: m.confirmCard || null,
        cartSelection: m.cartSelection || null,
        taskType: m.taskType || '',
        feedbackType: m.feedbackType || '',
        pending: false,
        streaming: false,
        errored: false,
        stopped: isTruncated,
        stoppedReason: isTruncated ? (m.stoppedReason || 'user_abort') : ''
      }
    },
    scrollToBottom() {
      if (this._scrollScheduled) return
      this._scrollScheduled = true
      setTimeout(() => {
        this._scrollScheduled = false
        this.scrollIntoId = ''
        this.$nextTick(() => { this.scrollIntoId = 'msg-bottom' })
      }, 80)
    }
  }
}
</script>

<style scoped>
.chat-page {
  min-height: 100vh;
  padding-bottom: 224rpx;
  background: #f4f8f8;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(16rpx + env(safe-area-inset-top)) 22rpx 16rpx;
  background: rgba(244, 248, 248, 0.94);
  backdrop-filter: blur(8px);
}
.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 6rpx 16rpx rgba(15, 118, 110, 0.08);
}
.title-wrap {
  flex: 1;
  overflow: hidden;
  text-align: center;
}
.title {
  overflow: hidden;
  color: #0f766e;
  font-size: 30rpx;
  font-weight: 800;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.messages {
  height: calc(100vh - 300rpx);
  padding: 8rpx 24rpx 0;
  box-sizing: border-box;
}
.msg-block {
  margin-bottom: 4rpx;
}
.cards-under {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin: -12rpx 0 26rpx 78rpx;
}
.bottom-anchor {
  height: 8rpx;
}
.input-bar {
  position: fixed;
  right: 0;
  bottom: 112rpx;
  left: 0;
  display: grid;
  grid-template-columns: 1fr 84rpx;
  gap: 16rpx;
  padding: 18rpx 24rpx calc(18rpx + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.98);
  border-top: 1rpx solid #e5e7eb;
  box-shadow: 0 -8rpx 28rpx rgba(15, 118, 110, 0.08);
  z-index: 20;
}
.input-wrap {
  display: flex;
  align-items: center;
  gap: 12rpx;
  height: 78rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  background: #f4f8f8;
  border: 1rpx solid #dbe5e3;
}
.chat-input {
  flex: 1;
  height: 78rpx;
  font-size: 28rpx;
}
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 78rpx;
  height: 78rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  box-shadow: 0 10rpx 24rpx rgba(20, 184, 166, 0.28);
}
.send-btn.disabled {
  background: #cbd5e1;
  box-shadow: none;
}
.stop-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 78rpx;
  height: 78rpx;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 10rpx 24rpx rgba(239, 68, 68, 0.28);
}
.stop-square {
  width: 26rpx;
  height: 26rpx;
  border-radius: 6rpx;
  background: #ffffff;
}
</style>
