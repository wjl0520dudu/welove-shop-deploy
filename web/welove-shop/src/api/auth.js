import request from '../utils/request'

export function sendCode(phone) {
  return request({ url: '/api/user/auth/sendCode', method: 'POST', data: { phone }, header: { 'content-type': 'application/x-www-form-urlencoded' } })
}
export function register(data) {
  return request({ url: '/api/user/auth/register', method: 'POST', data })
}
export function login(data) {
  return request({ url: '/api/user/auth/login', method: 'POST', data })
}
export function getProfile() {
  return request({ url: '/api/user/auth/profile', method: 'GET' })
}
export function updateProfile(data) {
  return request({ url: '/api/user/auth/update', method: 'POST', data })
}
export function changePassword(data) {
  // 微服务未提供独立改密接口，改密走 update 携带 password 字段
  return request({ url: '/api/user/auth/update', method: 'POST', data })
}
