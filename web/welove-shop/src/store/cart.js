import { reactive } from 'vue'
import { getCartCount, getCartList } from '../api/cart'

const TAB_BAR_CART_INDEX = 2

// 响应式 state：页面内绑定 cartStore.state.count 的地方能随加购实时刷新
const state = reactive({
  count: 0,
  items: []
})

function normalizeCount(value) {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : 0
}

export default {
  state,
  async refreshCount() {
    state.count = normalizeCount(await getCartCount())
    return state.count
  },
  async refreshAndSyncBadge() {
    await this.loadCart()
    return state.count
  },
  async loadCart() {
    const data = await getCartList()
    state.items = Array.isArray(data) ? data : (data?.records || data?.items || data?.list || [])
    state.count = state.items.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
    this.syncBadge(state.count)
    return state.items
  },
  /** 乐观更新：取数接口失败时也能让角标先动起来，返回更新后的值 */
  bump(delta = 1) {
    state.count = Math.max(0, Number(state.count || 0) + delta)
    this.syncBadge(state.count)
    return state.count
  },
  syncBadge(count = state.count) {
    const c = normalizeCount(count)
    state.count = c
    if (typeof uni === 'undefined') return c
    try {
      if (c > 0) {
        uni.setTabBarBadge({ index: TAB_BAR_CART_INDEX, text: String(c > 99 ? '99+' : c) })
      } else {
        uni.removeTabBarBadge({ index: TAB_BAR_CART_INDEX })
      }
    } catch (e) {
      // 部分运行端在 tabBar 尚未就绪时会抛错，状态仍先保持最新。
    }
    return c
  },
  reset() {
    state.count = 0
    state.items = []
    try {
      uni.removeTabBarBadge({ index: TAB_BAR_CART_INDEX })
    } catch (e) {
      // ignore
    }
  }
}
