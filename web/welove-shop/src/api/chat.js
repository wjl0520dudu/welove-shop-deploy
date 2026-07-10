import request from '../utils/request'
import { getToken } from '../utils/auth'
import { postEventStream } from '../utils/sse'

export function createConversation(title) {
  return request({ url: '/api/chat/chat/conversations', method: 'POST', data: { title }, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
export function getConversations() {
  return request({ url: '/api/chat/chat/conversations', method: 'GET' })
}
export function getMessages(conversationId) {
  return request({ url: '/api/chat/chat/messages', method: 'GET', data: { conversationId } })
}
export function sendMessage(data) {
  return request({ url: '/api/chat/chat/messages', method: 'POST', data })
}
export function deleteConversation(id) {
  return request({ url: `/api/chat/chat/conversations/${id}`, method: 'DELETE' })
}
export function updateConversation(id, params = {}) {
  // 后端以 @RequestParam 接收 title / isPinned，用查询串传递
  const query = Object.keys(params)
    .filter((k) => params[k] !== undefined && params[k] !== null)
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
    .join('&')
  const suffix = query ? `?${query}` : ''
  return request({ url: `/api/chat/chat/conversations/${id}${suffix}`, method: 'PUT' })
}

/** 消息点赞/点踩反馈 */
export function feedback(messageId, feedbackType) {
  return request({ url: '/api/chat/chat/messages/feedback', method: 'POST', data: { messageId, feedbackType } })
}

/**
 * 流式发送消息（SSE）
 *
 * uni.request 无法流式，故走 fetch + ReadableStream，手动注入 Bearer。
 * 事件命名做双向兼容映射后回调给页面。
 *
 * @param {object} payload  { userId, conversationId, content, username?, isAdmin?, gender?, skinType?, preferenceTags? }
 * @param {object} cb  { onOpen, onText, onProductCards, onConfirm, onCartSelection, onRouted, onDone, onError }
 * @returns {{ promise: Promise<void>, abort: () => void }}
 */
export function streamMessage(payload, cb = {}) {
  const token = getToken()
  return postEventStream('/api/chat/chat/stream/messages', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: payload,
    onOpen: cb.onOpen,
    onEvent: (frame) => dispatchChatEvent(frame, cb)
  })
}

function toArray(v) {
  if (Array.isArray(v)) return v
  if (v == null) return []
  return [v]
}

function pickText(obj, raw) {
  if (obj == null) return String(raw ?? '')
  if (typeof obj === 'string') return obj
  return obj.content ?? obj.text ?? obj.delta ?? obj.token ?? obj.answer ?? ''
}

/** 把一帧 SSE 事件按容错规则分派到对应回调，兼容多种事件命名 */
function dispatchChatEvent({ event, data }, cb) {
  let obj = null
  try { obj = JSON.parse(data) } catch (e) { obj = null }

  // 兼容包裹式：event 为通用 message，但 JSON 内自带 type/event 字段
  let type = (event || 'message').toLowerCase()
  if (type === 'message' && obj && (obj.type || obj.event)) {
    type = String(obj.type || obj.event).toLowerCase()
  }

  switch (type) {
    case 'token':
    case 'answer':
    case 'message':
    case 'delta':
      cb.onText && cb.onText(pickText(obj, data))
      break
    case 'product_card':
    case 'product_cards':
    case 'products':
      cb.onProductCards && cb.onProductCards(toArray(obj && (obj.productCards || obj.products || obj.data) || obj))
      break
    case 'confirm_card':
    case 'confirm':
      cb.onConfirm && cb.onConfirm((obj && (obj.confirmCard || obj.data)) || obj)
      break
    case 'cart_selection':
    case 'cart_list':
    case 'cart_selection_card':
      cb.onCartSelection && cb.onCartSelection((obj && (obj.cartSelection || obj.data)) || obj)
      break
    case 'routed':
    case 'route':
    case 'task_type':
      cb.onRouted && cb.onRouted((obj && (obj.taskType || obj.task_type)) || obj)
      break
    case 'end':
    case 'done':
    case 'complete':
      cb.onDone && cb.onDone(obj || {})
      break
    case 'error':
      cb.onError && cb.onError(obj || { message: data })
      break
    default:
      // 未知事件名但带文本，当作增量兜底
      if (obj && pickText(obj, '')) cb.onText && cb.onText(pickText(obj, data))
      break
  }
}
