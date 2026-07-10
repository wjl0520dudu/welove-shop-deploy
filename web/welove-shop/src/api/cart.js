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
export function checkAll(checked) {
  return request({ url: '/api/trade/cart/checkAll', method: 'POST', data: { checked }, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
