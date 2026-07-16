/**
 * "猜你想问" 推荐问题生成
 *
 * 依据当前季节 + 用户画像（肤质 / 性别 / 偏好标签）组合个性化购物问题，
 * 画像为空时回退到通用默认，保证空态始终有可点的引导问题。
 */

export function currentSeason(date = new Date()) {
  const m = date.getMonth() + 1
  if (m >= 3 && m <= 5) return 'spring'
  if (m >= 6 && m <= 8) return 'summer'
  if (m >= 9 && m <= 11) return 'autumn'
  return 'winter'
}

const SEASON_QUESTIONS = {
  spring: ['换季皮肤容易敏感，有什么温和的护肤品推荐？', '春天适合入手哪些清爽的日常单品？'],
  summer: ['夏天出油多，有什么控油又清爽的护肤品？', '想要一款防晒力强又不闷的防晒霜'],
  autumn: ['秋天干燥，帮我挑几款补水面膜', '换季想囤点保湿的，有什么推荐？'],
  winter: ['冬天特别干，有滋润度高的面霜推荐吗？', '天冷了想要保暖又好看的单品']
}

const SKIN_QUESTIONS = {
  敏感肌: '适合敏感肌的温和无刺激面霜有哪些？',
  干性: '干性皮肤想要长效保湿，有什么推荐？',
  油性: '油性皮肤怎么选控油又不拔干的产品？',
  混合性: '混合性皮肤 T 区油、两颊干，怎么护理？',
  中性: '中性皮肤日常护肤有什么值得入手的？'
}

const GENDER_QUESTIONS = {
  1: '有没有适合男士的清爽护理套装？',
  2: '帮我搭配一套适合日常的护肤流程'
}

const DEFAULT_QUESTIONS = [
  '帮我推荐适合敏感肌的保湿面霜',
  '200 元以内有什么值得买的耳机',
  '帮我对比几款热门商品',
  '最近有什么销量高的好物？'
]

function normalizeTags(tags) {
  if (!tags) return []
  if (Array.isArray(tags)) return tags.filter(Boolean)
  return String(tags).split(/[,，、\s]+/).filter(Boolean)
}

/**
 * @param {object} user  用户画像（gender / skinType / preferenceTags）
 * @param {object} [opts]
 * @param {number} [opts.limit=4]
 * @param {Date}   [opts.date]
 * @param {string[]} [opts.learnedQuestions] AI 侧根据跨会话偏好生成的问题
 * @returns {string[]} 去重后的推荐问题
 */
export function buildRecommendedQuestions(
  user = {},
  { limit = 4, date = new Date(), learnedQuestions = [] } = {}
) {
  const pool = []
  const season = currentSeason(date)

  normalizeTags(learnedQuestions).forEach((q) => pool.push(q))
  if (SEASON_QUESTIONS[season]) pool.push(SEASON_QUESTIONS[season][0])
  if (user.skinType && SKIN_QUESTIONS[user.skinType]) pool.push(SKIN_QUESTIONS[user.skinType])

  const tags = normalizeTags(user.preferenceTags)
  tags.slice(0, 2).forEach((tag) => pool.push(`有哪些${tag}的好物推荐？`))

  if (user.gender && GENDER_QUESTIONS[user.gender]) pool.push(GENDER_QUESTIONS[user.gender])
  if (SEASON_QUESTIONS[season] && SEASON_QUESTIONS[season][1]) pool.push(SEASON_QUESTIONS[season][1])

  // 补齐通用问题
  DEFAULT_QUESTIONS.forEach((q) => pool.push(q))

  const seen = new Set()
  const result = []
  for (const q of pool) {
    if (q && !seen.has(q)) {
      seen.add(q)
      result.push(q)
    }
    if (result.length >= limit) break
  }
  return result
}
