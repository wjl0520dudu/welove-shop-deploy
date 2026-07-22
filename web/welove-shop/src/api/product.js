import request from '../utils/request'

export function getProductList(params = {}) {
  return request({ url: '/api/product/product/list', method: 'GET', data: params })
}
export function getProductDetail(id) {
  return request({ url: `/api/product/product/${id}`, method: 'GET' })
}
export function getProductSkus(id) {
  return request({ url: `/api/product/product/${id}/skus`, method: 'GET' })
}
export function getProductReviews(id, limit = 10) {
  return request({ url: `/api/product/product/${id}/reviews`, method: 'GET', data: { limit } })
}
export function getProductFaqs(id) {
  return request({ url: `/api/product/product/${id}/faqs`, method: 'GET' })
}
export function getProductImages(id) {
  return request({ url: `/api/product/product/${id}/images`, method: 'GET' })
}
export function searchProducts(keywordOrParams, limit = 20) {
  const data = typeof keywordOrParams === 'object'
    ? keywordOrParams
    : { keyword: keywordOrParams, limit }
  return request({ url: '/api/product/product/search', method: 'GET', data })
}
export function getHotProducts(params = 10) {
  const data = typeof params === 'object' ? params : { limit: params }
  return request({ url: '/api/product/product/hot', method: 'GET', data })
}
export function submitReview(productId, dataOrRating, content) {
  const data = typeof dataOrRating === 'object'
    ? dataOrRating
    : { rating: dataOrRating, content }
  return request({ url: `/api/product/product/${productId}/reviews`, method: 'POST', data, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
