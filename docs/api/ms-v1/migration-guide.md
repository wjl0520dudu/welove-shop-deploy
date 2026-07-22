# 单体 → 微服务 API 路径映射

> 旧地址: `http://localhost:8888` (单体 Spring Boot) · 新地址: `http://localhost:8080` (网关)
>
> **规则:** 新路径 = `/api/{服务前缀}/{旧路径去掉/api/}`

---

## 一、用户与认证 (user-service)

### auth — 认证

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 发验证码 | `/api/auth/sendCode` | `/api/user/auth/sendCode` | POST | 否 |
| 手机登录 | `/api/auth/login` | `/api/user/auth/login` | POST | 否 |
| 刷新 token | `/api/auth/refresh` | `/api/user/auth/refresh` | POST | 否 |
| 获取用户信息 | `/api/auth/profile` | `/api/user/auth/profile` | GET | 是 |
| 更新用户资料 | `/api/auth/update` | `/api/user/auth/update` | POST | 是 |

> ⚠️ 旧单体有 `/api/auth/register` 和 `/api/auth/changePassword`, 微服务暂未实现 (骨架期手机号首次登录自动注册, 密码修改走 update).

### address — 收货地址

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 地址列表 | `/api/address/list` | `/api/user/address/list` | GET | 是 |
| 新增地址 | `/api/address/add` | `/api/user/address/add` | POST | 是 |
| 更新地址 | `/api/address/update` | `/api/user/address/update` | PUT | 是 |
| 删除地址 | `/api/address/delete?id=` | `/api/user/address/delete?id=` | DELETE | 是 |
| 设默认地址 | `/api/address/setDefault?id=` | `/api/user/address/setDefault?id=` | PUT | 是 |

### favorites — 收藏

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 添加收藏 | `/api/recommend/favorite/add` | `/api/user/favorites/{productId}` | POST | 是 |
| 取消收藏 | `/api/recommend/favorite/remove` | `/api/user/favorites/{productId}` | DELETE | 是 |
| 收藏列表 | `/api/recommend/favorite/list` | `/api/user/favorites` | GET | 是 |

> ⚠️ **路径变化较大**: 旧单体收藏混在 `/api/recommend/` 下, 微服务独立为 `/api/user/favorites/`, 且使用 RESTful 风格 `/{productId}` 而非 `?productId=`.

### browse-history — 浏览历史

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 上报浏览 | `/api/recommend/browse` | `/api/user/browse-history` | POST | 是 |
| 历史列表 | `/api/recommend/browse/history` | `/api/user/browse-history` | GET | 是 |
| 删除记录 | `/api/recommend/browse/history/{id}` | `/api/user/browse-history/{historyId}` | DELETE | 是 |

> ⚠️ **路径变化较大**: 旧单体混在 `/api/recommend/` 下, 微服务独立为 `/api/user/browse-history/`.

---

## 二、商品 (product-service)

### product — 商品

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 商品列表 | `/api/product/list` | `/api/product/product/list` | GET | 否 |
| 商品搜索 | `/api/product/search` | `/api/product/product/search` | GET | 否 |
| 热销商品 | `/api/product/hot` | `/api/product/product/hot` | GET | 否 |
| 商品详情 | `/api/product/{id}` | `/api/product/product/{id}` | GET | 否 |
| SKU 列表 | `/api/product/{id}/skus` | `/api/product/product/{id}/skus` | GET | 否 |
| 商品图片 | `/api/product/{id}/images` | `/api/product/product/{id}/images` | GET | 否 |
| 商品 FAQ | `/api/product/{id}/faqs` | `/api/product/product/{id}/faqs` | GET | 否 |
| 提交评价 | `/api/product/{id}/reviews` | `/api/product/product/{id}/reviews` | POST | 是 |

### category — 分类

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 分类列表 | `/api/category/list` | `/api/product/category/list` | GET | 否 |
| 分类详情 | `/api/category/{id}` | `/api/product/category/{id}` | GET | 否 |

### recommend-log — 推荐反馈

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 用户满意度反馈 | `/api/recommend/feedback` | `/api/product/recommend-log/{id}/feedback?value=` | PUT | 是 |

> ⚠️ **路径 + 方法变化**: 旧单体是 `POST /api/recommend/feedback` body 带 `{id, feedback}`.
> 微服务是 `PUT /api/product/recommend-log/{id}/feedback?value=0|1`.

---

## 三、交易 (trade-service)

### cart — 购物车

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 加入购物车 | `/api/cart/add` | `/api/trade/cart/add` | POST | 是 |
| 移除商品 | `/api/cart/remove` | `/api/trade/cart/remove` | DELETE | 是 |
| 按 ID 移除 | `/api/cart/removeById` | `/api/trade/cart/removeById` | DELETE | 是 |
| 更新数量 | `/api/cart/update` | `/api/trade/cart/update` | PUT | 是 |
| 切换 SKU | `/api/cart/updateSku` | `/api/trade/cart/updateSku` | PUT | 是 |
| 购物车列表 | `/api/cart/list` | `/api/trade/cart/list` | GET | 是 |
| 购物车数量 | `/api/cart/count` | `/api/trade/cart/count` | GET | 是 |
| 全选 | `/api/cart/checkAll` | `/api/trade/cart/checkAll` | POST | 是 |

> ⚠️ 微服务 **没有实现 checkAll 端点** (chats-service 里没有对应 Controller 方法). 前端需自行维护选中状态.

### order — 订单

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 创建订单 | `/api/order/create` | `/api/trade/order/create` | POST | 是 |
| 订单列表 | `/api/order/list` | `/api/trade/order/list` | GET | 是 |
| 订单详情 | `/api/order/{id}` | `/api/trade/order/{id}` | GET | 是 |
| 支付 | `/api/order/{id}/pay` | `/api/trade/order/{id}/pay` | PUT | 是 |
| 取消 | `/api/order/{id}/cancel` | `/api/trade/order/{id}/cancel` | PUT | 是 |
| 确认收货 | `/api/order/{id}/receive` | `/api/trade/order/{id}/receive` | PUT | 是 |
| 删除订单 | `/api/order/{id}` | `/api/trade/order/{id}` | DELETE | 是 |

---

## 四、对话 (chat-service)

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 创建对话 | `/api/chat/conversations` | `/api/chat/chat/conversations` | POST | 是 |
| 对话列表 | `/api/chat/conversations` | `/api/chat/chat/conversations` | GET | 是 |
| 发送消息 | `/api/chat/messages` | `/api/chat/chat/messages` | POST | 是 |
| 流式消息 | — | `/api/chat/chat/stream/messages` | POST | 是 |
| 消息列表 | `/api/chat/messages` | `/api/chat/chat/messages` | GET | 是 |
| 保存消息 | `/api/chat/messages/save` | — | — | — |
| 删除对话 | `/api/chat/conversations/{id}` | `/api/chat/chat/conversations/{id}` | DELETE | 是 |
| 更新对话 | `/api/chat/conversations/{id}` | `/api/chat/chat/conversations/{id}` | PUT | 是 |
| 消息反馈 | — | `/api/chat/chat/messages/feedback` | POST | 是 |

> ⚠️ 旧单体的 `/api/chat/messages/save` 在微服务中已不存在 — 消息由后端自动持久化, 前端不需单独保存.

---

## 五、管理后台 (admin-bff)

| 功能 | 旧单体 URL | 新微服务 URL | 方法 | 鉴权 |
|------|-----------|-------------|------|------|
| 管理员登录 | — | `/api/admin/login` | POST | 否 |
| Dashboard | — | `/api/admin/dashboard/stats` | GET | 是 (ADMIN) |

> admin 功能为微服务新增, 旧单体无对应接口.

---

## 六、前端适配要点

### 6.1 BASE_URL

```js
// 旧: utils/request.js
const BASE_URL = 'http://localhost:8888'

// 新: utils/request.js
const BASE_URL = ''   // Vite proxy: /api → :8080
```

### 6.2 Token 刷新

```js
// 旧
url: '/api/auth/refresh'

// 新
url: '/api/user/auth/refresh'
```

### 6.3 路径统一规则

旧单体路径形如 `/api/{领域}/{方法}`:
```
/api/auth/login
/api/product/list
/api/cart/add
```

新微服务路径形如 `/api/{服务前缀}/{领域}/{方法}`:
```
/api/user/auth/login        ← user-service
/api/product/product/list   ← product-service
/api/trade/cart/add         ← trade-service
/api/chat/chat/conversations ← chat-service
/api/admin/login            ← admin-bff
```

### 6.4 已删除/未实现的接口

| 旧 URL | 状态 | 替代方案 |
|--------|------|---------|
| `POST /api/auth/register` | 未实现 | 首次登录自动注册 |
| `POST /api/auth/changePassword` | 未实现 | `POST /api/user/auth/update` 带 `password` |
| `POST /api/chat/messages/save` | 已删除 | 后端自动持久化 |
| `POST /api/cart/checkAll` | 未实现 | 前端维护选中状态 |
| `POST /api/recommend/favorite/add` | 已迁移 | `POST /api/user/favorites/{productId}` |
| `POST /api/recommend/favorite/remove` | 已迁移 | `DELETE /api/user/favorites/{productId}` |
| `GET /api/recommend/favorite/list` | 已迁移 | `GET /api/user/favorites` |
| `POST /api/recommend/browse` | 已迁移 | `POST /api/user/browse-history` |
| `GET /api/recommend/browse/history` | 已迁移 | `GET /api/user/browse-history` |
| `DELETE /api/recommend/browse/history/{id}` | 已迁移 | `DELETE /api/user/browse-history/{historyId}` |
| `POST /api/recommend/feedback` | 已迁移 | `PUT /api/product/recommend-log/{id}/feedback?value=` |
