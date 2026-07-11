import { IMAGE_BASE_URL } from '../config/env'

const BASE_URL = IMAGE_BASE_URL
const FILE_NAME_PATTERN = /^[^/]+\.(png|jpe?g|webp|gif|bmp|svg)$/i

function encodePath(url) {
  return url.split('/').map((segment) => {
    if (!segment || segment.includes(':')) return segment
    try {
      return encodeURIComponent(decodeURIComponent(segment)).replace(/%2F/g, '/')
    } catch (error) {
      return encodeURIComponent(segment).replace(/%2F/g, '/')
    }
  }).join('/')
}

function imageAuthority() {
  const match = /^https?:\/\/([^/]+)/.exec(BASE_URL)
  return match ? match[1] : ''
}

function normalizeAbsoluteUrl(url) {
  const authority = imageAuthority()
  if (!authority) return url
  // 兼容历史数据：把指向网关端口的绝对图片地址改写到图片主机
  return url
    .replace('localhost:8080', authority)
    .replace('127.0.0.1:8080', authority)
}

export function buildImageUrl(url) {
  if (!url) return ''
  const raw = String(url).trim()
  if (!raw) return ''
  if (/^data:image\//.test(raw) || /^blob:/.test(raw)) return raw
  if (/^https?:\/\//.test(raw)) return encodePath(normalizeAbsoluteUrl(raw))

  const path = raw.startsWith('/')
    ? raw
    : FILE_NAME_PATTERN.test(raw)
      ? `/product-images/${raw}`
      : `/${raw}`

  return encodePath(`${BASE_URL}${path}`)
}

export function pickProductImage(product = {}) {
  return product.imageUrl || product.productImage || product.cover || product.product?.imageUrl || product.product?.productImage || ''
}
