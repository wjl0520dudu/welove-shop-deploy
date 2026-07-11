<template>
  <view class="page pwd-page">
    <view class="tip-card">
      <uni-icons type="locked" size="18" color="#0f766e" />
      <text>设置一个至少 6 位的新密码，保存后即可用手机号 + 密码登录。</text>
    </view>

    <view class="form-card">
      <view class="field">
        <text class="label">新密码</text>
        <input v-model="newPassword" class="input" type="password" placeholder="请输入新密码" maxlength="32" />
      </view>
      <view class="field">
        <text class="label">确认新密码</text>
        <input v-model="confirmPassword" class="input" type="password" placeholder="请再次输入新密码" maxlength="32" />
      </view>
      <text v-if="mismatch" class="err">两次输入的密码不一致</text>
    </view>

    <button class="save-btn" :class="{ disabled: !canSubmit }" :loading="loading" :disabled="loading || !canSubmit" @tap="submit">保存</button>
  </view>
</template>

<script>
import { changePassword } from '../../api/auth'
import { requireLogin } from '../../utils/routeGuard'

export default {
  data() {
    return { newPassword: '', confirmPassword: '', loading: false }
  },
  computed: {
    mismatch() {
      return Boolean(this.confirmPassword) && this.newPassword !== this.confirmPassword
    },
    canSubmit() {
      return this.newPassword.length >= 6 && this.newPassword === this.confirmPassword
    }
  },
  onLoad() {
    requireLogin('/pages/change-password/change-password')
  },
  methods: {
    async submit() {
      if (!this.canSubmit || this.loading) {
        if (this.newPassword.length < 6) uni.showToast({ title: '密码至少 6 位', icon: 'none' })
        else if (this.mismatch) uni.showToast({ title: '两次密码不一致', icon: 'none' })
        return
      }
      this.loading = true
      try {
        await changePassword({ password: this.newPassword })
        uni.showToast({ title: '密码已更新', icon: 'success' })
        setTimeout(() => uni.navigateBack(), 500)
      } catch (e) {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.pwd-page {
  min-height: 100vh;
  padding: 24rpx 24rpx calc(40rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: #f4f8f8;
}
.tip-card {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-bottom: 22rpx;
  padding: 22rpx 24rpx;
  border-radius: 20rpx;
  background: #f0fdfa;
  color: #0f766e;
  font-size: 24rpx;
  line-height: 1.5;
}
.form-card {
  padding: 12rpx 26rpx 26rpx;
  border-radius: 24rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(15, 118, 110, 0.07);
}
.field {
  padding: 24rpx 0;
  border-bottom: 1rpx solid #eef2f6;
}
.field:last-child {
  border-bottom: none;
}
.label {
  display: block;
  margin-bottom: 16rpx;
  color: #1f2937;
  font-size: 28rpx;
  font-weight: 800;
}
.input {
  height: 78rpx;
  padding: 0 24rpx;
  border-radius: 16rpx;
  background: #f4f8f8;
  border: 1rpx solid #dbe5e3;
  font-size: 28rpx;
}
.err {
  display: block;
  margin-top: 16rpx;
  color: #e17055;
  font-size: 23rpx;
}
.save-btn {
  height: 92rpx;
  margin-top: 30rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 92rpx;
  box-shadow: 0 14rpx 30rpx rgba(20, 184, 166, 0.24);
}
.save-btn.disabled {
  background: #cbd5e1;
  box-shadow: none;
}
</style>
