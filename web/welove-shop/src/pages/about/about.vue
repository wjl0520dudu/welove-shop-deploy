<template>
  <view class="page about-page">
    <view class="brand">
      <image class="logo" src="/static/logo.png" mode="aspectFit" />
      <text class="app-name">welove-shop</text>
      <text class="app-slogan">AI 智能导购 · 为你精选好物</text>
      <text class="app-version">版本 {{ version }}</text>
    </view>

    <view class="info-card">
      <view class="info-row">
        <text class="k">应用名称</text>
        <text class="v">welove-shop</text>
      </view>
      <view class="info-row">
        <text class="k">技术栈</text>
        <text class="v">uni-app · Vue 3 · 微服务</text>
      </view>
      <view class="info-row">
        <text class="k">当前版本</text>
        <text class="v">{{ version }}</text>
      </view>
    </view>

    <view class="desc-card">
      <text class="desc">
        welove-shop 是一款以对话式 AI 导购为核心的移动电商应用，通过理解你的预算、场景与偏好，帮你在海量商品中快速找到合适的好物，并支持从浏览、加购到下单的完整购物体验。
      </text>
    </view>

    <text class="copyright">© {{ year }} welove-shop</text>
  </view>
</template>

<script>
export default {
  data() {
    return {
      version: '1.0.0',
      year: 2026
    }
  }
}
</script>

<style scoped>
.about-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 48rpx 32rpx calc(40rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: radial-gradient(circle at 50% 0%, rgba(20, 184, 166, 0.12), transparent 42%), #f4f8f8;
}
.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0 48rpx;
}
.logo {
  width: 140rpx;
  height: 140rpx;
  border-radius: 34rpx;
  background: #ffffff;
  box-shadow: 0 18rpx 40rpx rgba(15, 118, 110, 0.14);
}
.app-name {
  margin-top: 24rpx;
  color: #0f766e;
  font-size: 40rpx;
  font-weight: 900;
  letter-spacing: 1rpx;
}
.app-slogan {
  margin-top: 12rpx;
  color: #667085;
  font-size: 26rpx;
}
.app-version {
  margin-top: 8rpx;
  color: #98a2b3;
  font-size: 23rpx;
}
.info-card {
  padding: 8rpx 26rpx;
  border-radius: 24rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(15, 118, 110, 0.07);
}
.info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 92rpx;
  border-bottom: 1rpx solid #f2f4f7;
}
.info-row:last-child {
  border-bottom: none;
}
.k {
  color: #667085;
  font-size: 27rpx;
}
.v {
  color: #1f2937;
  font-size: 27rpx;
  font-weight: 700;
}
.desc-card {
  margin-top: 22rpx;
  padding: 28rpx 26rpx;
  border-radius: 24rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(15, 118, 110, 0.07);
}
.desc {
  color: #475467;
  font-size: 26rpx;
  line-height: 1.7;
}
.copyright {
  margin-top: auto;
  padding-top: 40rpx;
  color: #b0b8c1;
  font-size: 22rpx;
  text-align: center;
}
</style>
