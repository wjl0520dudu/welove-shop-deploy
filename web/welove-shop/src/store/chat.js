import { createConversation, getConversations, getMessages } from '../api/chat'

/**
 * 把后端 Message 实体映射成前端渲染需要的统一形态。
 * 后端 status='truncated' → 前端 stopped=true(显示「已停止」标签)。
 */
function hydrateServerMessage(m) {
  const isTruncated = m && m.status === 'truncated'
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
}

const state = {
  currentConversation: null,   // { id, title, isPinned, ... }
  conversations: [],           // 抽屉列表
  messages: [],                // 当前会话消息（会话内内存缓存）
  streaming: false,
  loadingConversations: false,
  loadingMessages: false,
  /** 后台其他会话收到新消息时标记，触发会话列表红点提示（豆包式体验） */
  newMessageConvIds: new Set()
}

let creatingPromise = null     // create-if-none 记忆化，避免并发重复建会话

export default {
  state,
  setConversations(list) {
    state.conversations = Array.isArray(list) ? list : []
  },
  setCurrentConversation(conversation) {
    state.currentConversation = conversation
  },
  setMessages(list) {
    state.messages = Array.isArray(list) ? list : []
  },
  appendMessage(msg) {
    state.messages.push(msg)
  },
  patchLastAssistant(patch = {}) {
    for (let i = state.messages.length - 1; i >= 0; i--) {
      if (state.messages[i].role === 'assistant') {
        Object.assign(state.messages[i], patch)
        return state.messages[i]
      }
    }
    return null
  },
  setStreaming(v) {
    state.streaming = Boolean(v)
    return state.streaming
  },
  async loadConversations() {
    state.loadingConversations = true
    try {
      const list = await getConversations()
      state.conversations = Array.isArray(list) ? list : (list?.records || [])
      return state.conversations
    } finally {
      state.loadingConversations = false
    }
  },
  async openConversation(conversation) {
    state.currentConversation = conversation
    state.loadingMessages = true
    try {
      const list = await getMessages(conversation.id)
      // 把后端字段映射为前端渲染需要的统一形态(包含 stopped 等截断标记)
      const raw = Array.isArray(list) ? list : (list?.records || [])
      state.messages = raw.map(hydrateServerMessage)
      return state.messages
    } finally {
      state.loadingMessages = false
    }
  },
  /** 无当前会话时创建；并发调用共享同一个创建 Promise */
  async ensureConversation(title) {
    if (state.currentConversation && state.currentConversation.id) {
      return state.currentConversation
    }
    if (!creatingPromise) {
      creatingPromise = createConversation(title).finally(() => { creatingPromise = null })
    }
    const conv = await creatingPromise
    state.currentConversation = conv
    state.conversations = [conv, ...state.conversations]
    return conv
  },
  reset() {
    state.currentConversation = null
    state.conversations = []
    state.messages = []
    state.streaming = false
    creatingPromise = null
    state.newMessageConvIds = new Set()
  },
  /** 后台其他会话收到新消息时标记（豆包式红点） */
  markNewMessage(convId) {
    state.newMessageConvIds.add(Number(convId))
  },
  /** 用户切换到某会话时清除红点标记 */
  clearNewMessage(convId) {
    state.newMessageConvIds.delete(Number(convId))
  }
}
