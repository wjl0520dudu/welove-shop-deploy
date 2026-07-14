import axios from 'axios';

/**
 * admin-web 统一请求封装。
 *
 * baseURL 走 Vite dev 代理 /api → gateway:8080
 * 生产由 nginx 反代同源。
 *
 * 后端 Result 统一格式:
 *   { code: number, message: string, data: any }
 *   code === 0 表示成功
 *   code === 40001 (UNAUTHORIZED)  → 未登录/token 失效
 *   code === 60003 (NOT_ADMIN_TOKEN) → 非 ADMIN 角色
 */
const request = axios.create({
  baseURL: '/api/admin',
  timeout: 30000,
});

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('adminToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

request.interceptors.response.use(
  (response) => {
    const body = response.data;
    // 二进制/文件类接口直接返回原对象
    if (!body || typeof body !== 'object') return body;

    if (body.code === 0) {
      return body.data;
    }
    // 业务错误
    const err = new Error(body.message || `业务错误 code=${body.code}`);
    err.code = body.code;
    err.data = body.data;
    return Promise.reject(err);
  },
  (error) => {
    // HTTP 层错误
    const status = error?.response?.status;
    const body = error?.response?.data;
    const bizCode = body?.code;

    // 401 / 未登录 / 非 admin token 都跳回登录
    if (status === 401 || bizCode === 40001 || bizCode === 60003) {
      localStorage.removeItem('adminToken');
      localStorage.removeItem('adminInfo');
      // 避免死循环:已经在登录页就不跳
      if (!location.pathname.startsWith('/login')) {
        location.href = '/login';
      }
    }
    const msg = body?.message || error.message || '请求失败';
    const wrapped = new Error(msg);
    wrapped.status = status;
    wrapped.code = bizCode;
    return Promise.reject(wrapped);
  },
);

export default request;
