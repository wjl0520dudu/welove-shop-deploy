import request from './request';

// ==================== 登录 ====================
export const authApi = {
  login: (username, password) => request.post('/login', { username, password }),
};

// ==================== Dashboard ====================
export const dashboardApi = {
  stats: () => request.get('/dashboard/stats'),
};

// ==================== 用户管理 ====================
export const userApi = {
  list: (params) => request.get('/users', { params }),
  updateStatus: (id, status) =>
    request.put(`/users/${id}/status`, null, { params: { status } }),
};

// ==================== 商品管理 ====================
export const productApi = {
  list: (params) => request.get('/product/list', { params }),
  create: (data) => request.post('/product', data),
  updateStatus: (id, status) =>
    request.put(`/product/${id}/status`, null, { params: { status } }),
  update: (id, data) => request.put(`/product/${id}`, data),
  stats: () => request.get('/product/stats'),
  brands: () => request.get('/product/brands'),
};

// ==================== 订单管理 ====================
export const orderApi = {
  list: (params) => request.get('/order/list', { params }),
  items: (id) => request.get(`/order/${id}/items`),
  stats: () => request.get('/order/stats'),
};

// ==================== 会话管理 ====================
export const conversationApi = {
  list: (params) => request.get('/conversation/list', { params }),
  messages: (id) => request.get(`/conversation/${id}/messages`),
  stats: () => request.get('/conversation/stats'),
  delete: (id) => request.delete(`/conversation/${id}`),
};

// ==================== 公告管理 ====================
export const noticeApi = {
  list: (params) => request.get('/notice/list', { params }),
  add: (data) => request.post('/notice/add', data),
  update: (data) => request.put('/notice/update', data),
  delete: (id) => request.delete(`/notice/delete/${id}`),
};

// ==================== Agent 监控 ====================
export const agentApi = {
  runs: (params) => request.get('/agent/runs', { params }),
  runDetail: (runId) => request.get(`/agent/runs/${runId}`),
  runSteps: (runId) => request.get(`/agent/runs/${runId}/steps`),
  toolCalls: (params) => request.get('/agent/tool-calls', { params }),
  failedToolCalls: (limit = 10) =>
    request.get('/agent/tool-calls/failed', { params: { limit } }),
};

// ==================== QA 日志/未回答 ====================
export const qaApi = {
  logs: (params) => request.get('/qa/logs', { params }),
  unanswered: () => request.get('/qa/unanswered/list'),
};

// ==================== 知识库管理 ====================
export const knowledgeApi = {
  list: (categoryId) =>
    request.get('/knowledge/list', {
      params: categoryId ? { categoryId } : {},
    }),
  delete: (id) => request.delete(`/knowledge/${id}`),
  retryParse: (id, filePath) =>
    request.post('/knowledge/retry-parse', { id, filePath }),
};

// ==================== 知识巡检 ====================
export const inspectionApi = {
  unanswered: (params) =>
    request.get('/knowledge-inspection/unanswered/analyze', { params }),
  library: (params) =>
    request.get('/knowledge-inspection/library/analyze', { params }),
};

// ==================== 推荐效果统计 ====================
export const recommendApi = {
  stats: () => request.get('/recommend/stats'),
  logs: (params) => request.get('/recommend/logs', { params }),
};
