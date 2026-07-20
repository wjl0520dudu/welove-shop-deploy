import { login as loginApi, getProfile } from '../api/auth'
import { clearAuth, getRefreshToken, getStoredUser, getToken, setRefreshToken, setStoredUser, setToken } from '../utils/auth'
import chatStore from './chat'
import cartStore from './cart'

const state = {
  token: '',
  refreshToken: '',
  user: null
}

function readToken(data = {}) {
  return data.token || data.accessToken || ''
}

function applyAuth(data = {}) {
  state.token = readToken(data)
  state.refreshToken = data.refreshToken || ''
  state.user = data.user || null
  setToken(state.token)
  setRefreshToken(state.refreshToken)
  setStoredUser(state.user)
}

export default {
  state,
  restore() {
    state.token = getToken()
    state.refreshToken = getRefreshToken()
    state.user = getStoredUser()
  },
  isLoggedIn() {
    return Boolean(state.token || getToken())
  },
  async login(payload) {
    const data = await loginApi(payload)
    applyAuth(data)
    return data
  },
  /**
   * 测试登录:服务端已返回完整 { token, refreshToken, user },直接落本地即可。
   * 与 login() 区别:不调用 loginApi,不走短信验证码。
   */
  async handleTestLogin(data) {
    applyAuth(data)
    return data
  },
  async loadProfile() {
    const user = await getProfile()
    state.user = user
    setStoredUser(user)
    return user
  },
  logout() {
    state.token = ''
    state.refreshToken = ''
    state.user = null
    clearAuth()
    chatStore.reset()
    cartStore.reset()
  }
}
