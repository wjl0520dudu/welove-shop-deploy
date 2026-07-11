import request from '../utils/request'

export function addCart(productId, skuId) {
  return request({ url: '/api/trade/cart/add', method: 'POST', data: { productId, skuId }, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
export function removeCart(productId, quantity) {
  return request({ url: '/api/trade/cart/remove', method: 'DELETE', data: { productId, quantity } })
}
export function removeCartById(cartItemId) {
  return request({ url: '/api/trade/cart/removeById', method: 'DELETE', data: { cartItemId } })
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
