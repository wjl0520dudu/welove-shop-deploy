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
    // 保留用户多模态消息的图片地址，切换会话/刷新后 MessageBubble 才能回显。
    imageUrl: m.imageUrl || m.image_url || '',
    productCards: m.productCards || [],
    confirmCard: m.confirmCard || null,
    cartSelection: m.cartSelection || null,
    agentMeta: m.agentMeta || m.agent_meta || null,
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
  messagesByConversationId: {},
  activeStreams: {},
  streaming: false,
  streamVersion: 0,
  loadingConversations: false,
  loadingMessages: false,
  /** 后台其他会话收到新消息时标记，触发会话列表红点提示（豆包式体验） */
  newMessageConvIds: [],       // 用 Array 而非 Set——Set 的 add/delete 不触发 Vue3 响应式
  newMessageVersion: 0         // 版本号，每次增删时 ++，触发组件更新
}

let creatingPromise = null     // create-if-none 记忆化，避免并发重复建会话

function convKey(convId) {
  return convId == null ? '' : String(convId)
}

function refreshStreamingFlag() {
  state.streaming = Object.keys(state.activeStreams).length > 0
  state.streamVersion++
  return state.streaming
}

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
  setConversationMessages(convId, list) {
    const key = convKey(convId)
    if (!key) return []
    state.messagesByConversationId[key] = Array.isArray(list) ? list : []
    return state.messagesByConversationId[key]
  },
  getConversationMessages(convId) {
    const key = convKey(convId)
    return key ? state.messagesByConversationId[key] : null
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
  startStream(convId, record = {}) {
    const key = convKey(convId)
    if (!key) return null
    state.activeStreams[key] = {
      conversationId: convId,
      handle: null,
      assistant: null,
      messages: null,
      userAborted: false,
      status: 'streaming',
      ...record
    }
    refreshStreamingFlag()
    return state.activeStreams[key]
  },
  updateStream(convId, patch = {}) {
    const record = this.getStream(convId)
    if (!record) return null
    Object.assign(record, patch)
    state.streamVersion++
    return record
  },
  finishStream(convId) {
    const key = convKey(convId)
    if (key && state.activeStreams[key]) delete state.activeStreams[key]
    return refreshStreamingFlag()
  },
  getStream(convId) {
    const key = convKey(convId)
    return key ? state.activeStreams[key] : null
  },
  isStreaming(convId) {
    void state.streamVersion
    const key = convKey(convId)
    return Boolean(key && state.activeStreams[key])
  },
  hasActiveStreams() {
    void state.streamVersion
    return Object.keys(state.activeStreams).length > 0
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
      this.setConversationMessages(conversation.id, state.messages)
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
    state.messagesByConversationId = {}
    state.activeStreams = {}
    state.streaming = false
    state.streamVersion = 0
    creatingPromise = null
    state.newMessageConvIds = []
    state.newMessageVersion = 0
  },
  /** 后台其他会话收到新消息时标记（豆包式红点） */
  markNewMessage(convId) {
    const id = Number(convId)
    if (!state.newMessageConvIds.includes(id)) {
      state.newMessageConvIds.push(id)
      state.newMessageVersion++
    }
  },
  /** 用户切换到某会话时清除红点标记 */
  clearNewMessage(convId) {
    const id = Number(convId)
    const idx = state.newMessageConvIds.indexOf(id)
    if (idx !== -1) {
      state.newMessageConvIds.splice(idx, 1)
      state.newMessageVersion++
    }
  }
}
