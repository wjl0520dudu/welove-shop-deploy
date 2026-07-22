import request from '../utils/request'

function toQuery(data = {}) {
  return Object.keys(data)
    .filter((key) => data[key] !== undefined && data[key] !== null)
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(data[key])}`)
    .join('&')
}

export function addCart(productId, skuId) {
  return request({ url: '/api/trade/cart/add', method: 'POST', data: { productId, skuId }, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
// DELETE 接口后端用 @RequestParam 接收,必须把参数拼到 query string,
/** 按商品 ID 删除(quantity 不传则整条移除,传则递减) */
export function removeCart(productId, quantity) {
  const query = toQuery({ productId, quantity })
  return request({ url: `/api/trade/cart/remove${query ? `?${query}` : ''}`, method: 'DELETE' })
}
/** 按购物车条目 ID 删除 */
export function removeCartById(cartItemId) {
  const query = toQuery({ cartItemId })
  return request({ url: `/api/trade/cart/removeById${query ? `?${query}` : ''}`, method: 'DELETE' })
}
export function updateQuantity(productId, quantity) {
  return request({ url: '/api/trade/cart/update', method: 'PUT', data: { productId, quantity }, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
export function updateSku(productId, oldSkuId, newSkuId) {
  return request({ url: '/api/trade/cart/updateSku', method: 'PUT', data: { productId, oldSkuId, newSkuId }, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
export function getCartList() {
  return request({ url: '/api/trade/cart/list', method: 'GET' })
}
export function getCartCount() {
  return request({ url: '/api/trade/cart/count', method: 'GET' })
}
/**
 * 全选/取消全选 —— 微服务未实现服务端接口，选中状态由前端本地维护。
 * 保留同名方法以兼容调用方，直接返回已完成的 Promise，不产生网络请求。
 */
export function checkAll(checked) {
  return Promise.resolve({ checked })
}
