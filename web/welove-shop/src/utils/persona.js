/**
 * 用户画像取值集 —— 用户画像向导与资料编辑共用，避免重复定义
 */

export const GENDERS = [
  { value: 1, label: '男' },
  { value: 2, label: '女' },
  { value: 0, label: '不想说' }
]

export const AGE_RANGES = ['18-24', '25-30', '31-40', '40+']

export const SKIN_TYPES = ['干性', '油性', '混合性', '中性', '敏感肌']

export const PREFERENCE_GROUPS = [
  { title: '风格', tags: ['简约', '精致', '潮流', '复古', '运动', '甜美'] },
  { title: '偏好', tags: ['高性价比', '品质优先', '新品尝鲜', '大牌之选', '小众独特'] },
  { title: '关注', tags: ['保湿补水', '控油清爽', '提亮美白', '紧致抗老', '温和修护', '敏感适用'] }
]

export function genderLabel(value) {
  const map = { 1: '男', 2: '女', 0: '不想说' }
  return map[value] || ''
}

export function normalizeTags(tags) {
  if (!tags) return []
  if (Array.isArray(tags)) return tags.filter(Boolean)
  return String(tags).split(/[,，、\s]+/).filter(Boolean)
}
