import request from '../utils/request'

/** 推荐反馈 — product-service */
export function feedback(id, feedbackValue) {
  return request({ url: `/api/product/recommend-log/${id}/feedback?value=${encodeURIComponent(feedbackValue)}`, method: 'PUT' })
}

/** 上报浏览记录 — user-service */
export function recordBrowse(data) {
  return request({ url: '/api/user/browse-history', method: 'POST', data })
}

/** 收藏 — user-service */
export function addFavorite(productId) {
  return request({ url: `/api/user/favorites/${productId}`, method: 'POST' })
}
export function removeFavorite(productId) {
  return request({ url: `/api/user/favorites/${productId}`, method: 'DELETE' })
}
export function getFavoriteList() {
  return request({ url: '/api/user/favorites', method: 'GET' })
}

/** 浏览历史 — user-service */
export function getBrowseHistory() {
  return request({ url: '/api/user/browse-history', method: 'GET' })
}
export function deleteBrowseHistory(id) {
  return request({ url: `/api/user/browse-history/${id}`, method: 'DELETE' })
}
