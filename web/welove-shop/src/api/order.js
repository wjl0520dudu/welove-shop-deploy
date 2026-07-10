import request from '../utils/request'

export function createOrder(data) {
  return request({ url: '/api/trade/order/create', method: 'POST', data })
}
export function getOrderList(params = {}) {
  return request({ url: '/api/trade/order/list', method: 'GET', data: params })
}
export function getOrderDetail(id) {
  return request({ url: `/api/trade/order/${id}`, method: 'GET' })
}
export function payOrder(id) {
  return request({ url: `/api/trade/order/${id}/pay`, method: 'PUT' })
}
export function cancelOrder(id) {
  return request({ url: `/api/trade/order/${id}/cancel`, method: 'PUT' })
}
export function receiveOrder(id) {
  return request({ url: `/api/trade/order/${id}/receive`, method: 'PUT' })
}
export function deleteOrder(id) {
  return request({ url: `/api/trade/order/${id}`, method: 'DELETE' })
}
