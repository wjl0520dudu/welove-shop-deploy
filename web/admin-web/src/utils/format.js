/**
 * 通用格式化工具。
 */

export function fmtDateTime(v) {
  if (!v) return '-';
  try {
    const d = new Date(v);
    if (isNaN(d.getTime())) return String(v);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch {
    return String(v);
  }
}

export function fmtDate(v) {
  if (!v) return '-';
  try {
    const d = new Date(v);
    if (isNaN(d.getTime())) return String(v);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  } catch {
    return String(v);
  }
}

export function fmtMoney(v) {
  if (v == null) return '¥0.00';
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return `¥${n.toFixed(2)}`;
}

/** 订单状态映射。 */
export const ORDER_STATUS = {
  0: { label: '待付款', badge: 'badge-warn' },
  1: { label: '待发货', badge: 'badge-info' },
  2: { label: '待收货', badge: 'badge-info' },
  3: { label: '已完成', badge: 'badge-success' },
  4: { label: '已取消', badge: 'badge-muted' },
};

/** 用户状态映射。 */
export const USER_STATUS = {
  1: { label: '正常', badge: 'badge-success' },
  0: { label: '禁用', badge: 'badge-danger' },
};

/** 商品状态映射。 */
export const PRODUCT_STATUS = {
  1: { label: '在售', badge: 'badge-success' },
  0: { label: '下架', badge: 'badge-muted' },
};

/** 简单确认弹窗（原生 confirm 兜底）。 */
export function confirmAction(msg) {
  return window.confirm(msg);
}

/** 简单提示（原生 alert 兜底）。 */
export function toast(msg) {
  window.alert(msg);
}

/** 截断长文本。 */
export function ellipsis(s, len = 50) {
  if (!s) return '';
  return s.length > len ? s.slice(0, len) + '…' : s;
}

/**
 * 图片 URL 构建 —— 与 H5 前端 uni-app 端对齐。
 *
 * 绝对 URL(http(s)://) 原样返回；
 * 相对路径 + 文件名拼 CDN 前缀。
 */
const IMAGE_BASE_URL = window.__WLS_RUNTIME_CONFIG__?.IMAGE_BASE_URL || (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_IMAGE_BASE_URL)
  || 'https://liangwenjun.oss-cn-hangzhou.aliyuncs.com';

export function buildImageUrl(url) {
  if (!url) return '';
  const raw = String(url).trim();
  if (!raw) return '';
  if (/^https?:\/\//.test(raw)) return raw;
  if (/^data:image\//.test(raw) || /^blob:/.test(raw)) return raw;
  const path = raw.startsWith('/') ? raw : '/' + raw;
  return IMAGE_BASE_URL + path;
}
