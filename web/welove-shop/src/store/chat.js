import { createConversation, getConversations, getMessages } from '../api/chat'

const state = {
  currentConversation: null,   // { id, title, isPinned, ... }
  conversations: [],           // 抽屉列表
  messages: [],                // 当前会话消息（会话内内存缓存）
  streaming: false,
  loadingConversations: false,
  loadingMessages: false
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
      state.messages = Array.isArray(list) ? list : (list?.records || [])
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
  }
}
