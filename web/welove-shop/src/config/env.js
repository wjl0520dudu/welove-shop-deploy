/**
 * 全局环境配置 —— H5 单点配置
 *
 * 开发期 API 走 Vite 代理（/api → 网关 :8080）；生产由 nginx 同源反代，
 * 故 API_BASE_URL 留空即可在两种环境下同源命中 /api。
 * 未来若需跨域直连网关，只改这一处。
 */
export const API_BASE_URL = ''

/**
 * 商品图片主机
 *
 * 商品/购物车接口返回的 imageUrl 为相对路径（如 /img/p1.jpg 或裸文件名），
 * 前端在此拼接主机后展示。云存储 / CDN 供应商尚未确定，暂指向本地资源服务；
 * 未来切换到云存储只需修改此常量。
 */
export const IMAGE_BASE_URL = 'http://localhost:8888'
