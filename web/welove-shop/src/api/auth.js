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
  return request({ url: '/api/user/auth/changePassword', method: 'POST', data })
}
