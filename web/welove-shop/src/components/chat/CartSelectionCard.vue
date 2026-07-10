<template>
  <view class="cart-card">
    <view class="head">
      <text class="title">{{ card.title || '为你挑选，确认加入购物车' }}</text>
      <view class="select-all" @tap="toggleAll">
        <view class="checkbox" :class="{ checked: allChecked }">
          <uni-icons v-if="allChecked" type="checkmarkempty" size="13" color="#ffffff" />
        </view>
        <text>全选</text>
      </view>
    </view>

    <view class="list">
      <view
        v-for="(item, index) in items"
        :key="item.productId || index"
        class="item"
        @tap="toggle(index)"
      >
        <view class="checkbox" :class="{ checked: item._checked }">
          <uni-icons v-if="item._checked" type="checkmarkempty" size="13" color="#ffffff" />
        </view>
        <image
          v-if="item.image && !failed[index]"
          class="thumb"
          :src="item.image"
          mode="aspectFill"
          @error="onError(index)"
        />
        <view v-else class="thumb placeholder">
          <uni-icons type="image" size="22" color="#98a2b3" />
        </view>
        <view class="info">
          <text class="name">{{ item.title }}</text>
          <text v-if="item.spec" class="spec">{{ item.spec }}</text>
          <view class="price-row">
            <text class="price">¥{{ item.price }}</text>
            <text class="qty">x{{ item.quantity }}</text>
          </view>
        </view>
      </view>
    </view>

    <view class="footer">
      <text class="count">已选 {{ checkedCount }} 件</text>
      <view class="submit" :class="{ disabled: checkedCount === 0 }" @tap="submit">
        <uni-icons type="cart-filled" size="16" color="#ffffff" />
        <text>加入购物车</text>
      </view>
    </view>
  </view>
</template>

<script>
import { formatMoney } from '../../utils/format'
import { buildImageUrl, pickProductImage } from '../../utils/image'

export default {
  name: 'CartSelectionCard',
  props: {
    card: { type: Object, default: () => ({}) }
  },
  emits: ['submit'],
  data() {
    return { items: [], failed: {} }
  },
  computed: {
    checkedCount() {
      return this.items.filter((i) => i._checked).length
    },
    allChecked() {
      return this.items.length > 0 && this.items.every((i) => i._checked)
    }
  },
  watch: {
    card: {
      immediate: true,
      handler() { this.hydrate() }
    }
  },
  methods: {
    hydrate() {
      const raw = (this.card && (this.card.items || this.card.products || this.card.list)) || []
      this.items = raw.map((p) => ({
        productId: p.productId || p.id,
        skuId: p.skuId || p.sku_id || null,
        title: p.title || p.name || p.productTitle || '商品',
        spec: p.skuProperties || p.spec || '',
        price: formatMoney(p.price ?? p.basePrice ?? p.skuPrice ?? 0),
        quantity: Number(p.quantity || 1),
        image: buildImageUrl(pickProductImage(p)),
        _checked: p.selected !== false,
        raw: { ...p, id: p.productId || p.id }
      }))
      this.failed = {}
    },
    toggle(index) {
      this.items[index]._checked = !this.items[index]._checked
    },
    toggleAll() {
      const next = !this.allChecked
      this.items.forEach((i) => { i._checked = next })
    },
    onError(index) {
      this.failed = { ...this.failed, [index]: true }
    },
    submit() {
      const selected = this.items.filter((i) => i._checked).map((i) => i.raw)
      if (!selected.length) return
      this.$emit('submit', selected)
    }
  }
}
</script>

<style scoped>
.cart-card {
  padding: 20rpx 22rpx;
  border-radius: 20rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 28rpx rgba(15, 118, 110, 0.1);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title {
  flex: 1;
  color: #1f2937;
  font-size: 26rpx;
  font-weight: 700;
}
.select-all {
  display: flex;
  align-items: center;
  gap: 8rpx;
  color: #667085;
  font-size: 23rpx;
}
.checkbox {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34rpx;
  height: 34rpx;
  border: 2rpx solid #cbd5e1;
  border-radius: 50%;
  background: #ffffff;
}
.checkbox.checked {
  border-color: #14b8a6;
  background: #14b8a6;
}
.list {
  margin-top: 12rpx;
}
.item {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 14rpx 0;
  border-top: 1rpx solid #f2f4f7;
}
.thumb {
  width: 96rpx;
  height: 96rpx;
  border-radius: 14rpx;
  background: #eef6f5;
}
.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
}
.info {
  flex: 1;
  min-width: 0;
}
.name {
  display: block;
  overflow: hidden;
  color: #1f2937;
  font-size: 25rpx;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.spec {
  display: block;
  margin-top: 4rpx;
  color: #98a2b3;
  font-size: 21rpx;
}
.price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8rpx;
}
.price {
  color: #f97316;
  font-size: 26rpx;
  font-weight: 800;
}
.qty {
  color: #98a2b3;
  font-size: 22rpx;
}
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16rpx;
}
.count {
  color: #667085;
  font-size: 23rpx;
}
.submit {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 14rpx 30rpx;
  border-radius: 999rpx;
  background: #14b8a6;
  color: #ffffff;
  font-size: 25rpx;
  font-weight: 700;
}
.submit.disabled {
  background: #cbd5e1;
}
</style>
