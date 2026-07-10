<template>
  <view class="page edit-page">
    <view class="form-card">
      <view class="field">
        <text class="label">昵称</text>
        <input v-model="form.username" class="input" placeholder="设置一个昵称" maxlength="20" />
      </view>

      <view class="field">
        <text class="label">性别</text>
        <view class="pill-row">
          <view
            v-for="g in genders"
            :key="g.value"
            class="pill"
            :class="{ active: form.gender === g.value }"
            @tap="form.gender = g.value"
          >{{ g.label }}</view>
        </view>
      </view>

      <view class="field">
        <text class="label">年龄段</text>
        <view class="pill-row">
          <view
            v-for="age in ageRanges"
            :key="age"
            class="pill"
            :class="{ active: form.ageRange === age }"
            @tap="form.ageRange = age"
          >{{ age }}</view>
        </view>
      </view>

      <view class="field">
        <text class="label">肤质</text>
        <view class="pill-row">
          <view
            v-for="skin in skinTypes"
            :key="skin"
            class="pill"
            :class="{ active: form.skinType === skin }"
            @tap="form.skinType = skin"
          >{{ skin }}</view>
        </view>
      </view>
    </view>

    <view class="form-card">
      <text class="section-title">偏好标签</text>
      <view v-for="group in preferenceGroups" :key="group.title" class="tag-group">
        <text class="group-title">{{ group.title }}</text>
        <view class="pill-row">
          <view
            v-for="tag in group.tags"
            :key="tag"
            class="pill"
            :class="{ active: form.preferenceTags.includes(tag) }"
            @tap="toggleTag(tag)"
          >{{ tag }}</view>
        </view>
      </view>
    </view>

    <button class="save-btn" :loading="loading" :disabled="loading" @tap="save">保存</button>
  </view>
</template>

<script>
import { updateProfile } from '../../api/auth'
import userStore from '../../store/user'
import { requireLogin } from '../../utils/routeGuard'
import { GENDERS, AGE_RANGES, SKIN_TYPES, PREFERENCE_GROUPS, normalizeTags } from '../../utils/persona'

export default {
  data() {
    return {
      loading: false,
      genders: GENDERS,
      ageRanges: AGE_RANGES,
      skinTypes: SKIN_TYPES,
      preferenceGroups: PREFERENCE_GROUPS,
      form: {
        username: '',
        gender: null,
        ageRange: '',
        skinType: '',
        preferenceTags: []
      }
    }
  },
  onLoad() {
    if (!requireLogin('/pages/profile-edit/profile-edit')) return
    this.prefill()
  },
  methods: {
    prefill() {
      const u = userStore.state.user || {}
      this.form.username = u.username || ''
      this.form.gender = (u.gender === null || u.gender === undefined) ? null : u.gender
      this.form.ageRange = u.ageRange || ''
      this.form.skinType = u.skinType || ''
      this.form.preferenceTags = normalizeTags(u.preferenceTags)
    },
    toggleTag(tag) {
      const i = this.form.preferenceTags.indexOf(tag)
      if (i >= 0) this.form.preferenceTags.splice(i, 1)
      else this.form.preferenceTags.push(tag)
    },
    async save() {
      if (this.loading) return
      this.loading = true
      const payload = {
        username: this.form.username.trim(),
        ageRange: this.form.ageRange,
        skinType: this.form.skinType,
        preferenceTags: this.form.preferenceTags
      }
      if (this.form.gender !== null && this.form.gender !== undefined) payload.gender = this.form.gender
      try {
        const user = await updateProfile(payload)
        userStore.state.user = user
        uni.showToast({ title: '已保存', icon: 'success' })
        setTimeout(() => uni.navigateBack(), 500)
      } catch (e) {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.edit-page {
  min-height: 100vh;
  padding: 24rpx 24rpx calc(40rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: #f4f8f8;
}
.form-card {
  margin-bottom: 22rpx;
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
  height: 72rpx;
  padding: 0 24rpx;
  border-radius: 16rpx;
  background: #f4f8f8;
  border: 1rpx solid #dbe5e3;
  font-size: 28rpx;
}
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.pill {
  padding: 16rpx 28rpx;
  border: 2rpx solid #e4e7ec;
  border-radius: 999rpx;
  background: #ffffff;
  color: #344054;
  font-size: 26rpx;
  font-weight: 700;
}
.pill.active {
  border-color: #14b8a6;
  background: #14b8a6;
  color: #ffffff;
}
.section-title {
  display: block;
  margin: 16rpx 0 6rpx;
  color: #1f2937;
  font-size: 28rpx;
  font-weight: 900;
}
.tag-group {
  margin-top: 20rpx;
}
.group-title {
  display: block;
  margin-bottom: 14rpx;
  color: #98a2b3;
  font-size: 24rpx;
  font-weight: 800;
}
.save-btn {
  height: 92rpx;
  margin-top: 12rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 92rpx;
  box-shadow: 0 14rpx 30rpx rgba(20, 184, 166, 0.24);
}
</style>
