# welove-shop-agt API 文档

> 版本: v0.3 · 最后更新: 2026-07-11 · 架构: Spring Cloud 微服务 + Plan A (/api 归属网关层)

---

## 一、架构概览

```
前端 (uni-app H5, :5173)
  │  /api/{service}/...
  ▼
Vite Proxy (/api → :8080)          ← 开发环境
  │                                  生产环境替换为 nginx
  ▼
Gateway (:8080)                    ← Spring Cloud Gateway
  │  StripPrefix=2: 剥离 /api/{service}
  │  例如 /api/user/auth/login → /auth/login
  ├── /api/user/**    → user-service      注册中心: Nacos
  ├── /api/product/** → product-service
  ├── /api/trade/**   → trade-service
  ├── /api/chat/**    → chat-service
  ├── /api/admin/**   → admin-bff
  └── (ai-service 不经过 Gateway,直接 :8000)
```

## 二、通用约定

### 2.1 统一响应体 `Result<T>`

**所有 HTTP 200 响应**都遵循此格式:

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `int` | 0 = 成功, 非 0 = 错误 (见 §2.3) |
| `message` | `String` | 成功时 `"success"`, 失败时为错误描述 |
| `data` | `T` | 业务载荷, 失败时为 `null` |

示例:
```json
// 成功
{ "code": 0, "message": "success", "data": { "id": 1, "username": "张三" } }

// 失败
{ "code": 10002, "message": "认证失败,请重新登录", "data": null }
```

### 2.2 鉴权

| 机制 | 说明 |
|------|------|
| 鉴权方式 | JWT (HS256), 存于 `Authorization: Bearer <token>` 请求头 |
| 当前策略 | 服务侧鉴权 (JwtInterceptor), gateway 透传 |

**匿名端点** (无需 token):
- `POST /api/user/auth/sendCode`
- `POST /api/user/auth/login`
- `POST /api/user/auth/refresh`
- `GET /api/product/product/list`
- `GET /api/product/product/search`
- `GET /api/product/product/hot`
- `GET /api/product/product/{id}` (含 SKU/图片/FAQ)
- `GET /api/product/product/batch`
- `GET /api/product/category/**`
- `GET /api/chat/notice/latest`
- `POST /api/admin/login`

**管理员端点** 额外要求 JWT claims 中 `role = "ADMIN"`.

### 2.3 错误码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 10001 | 参数校验失败 |
| 10002 | 未认证 / token 无效 |
| 10003 | 无权限 |
| 10004 | 资源不存在 |
| 10500 | 服务器内部错误 |
| 60001 | 用户名或密码错误 (admin) |
| 60003 | 非管理员 token (admin) |

### 2.4 分页响应 `IPage<T>`

| 字段 | 类型 | 说明 |
|------|------|------|
| `records` | `Array<T>` | 当前页数据 |
| `total` | `long` | 总记录数 |
| `size` | `long` | 每页大小 |
| `current` | `long` | 当前页码 |
| `pages` | `long` | 总页数 |

---

## 三、服务文档索引

| 服务 | 网关前缀 | 文档 |
|------|---------|------|
| user-service | `/api/user` | [user-service.md](user-service.md) |
| product-service | `/api/product` | [product-service.md](product-service.md) |
| trade-service | `/api/trade` | [trade-service.md](trade-service.md) |
| chat-service | `/api/chat` | [chat-service.md](chat-service.md) |
| admin-bff | `/api/admin` | [admin-bff.md](admin-bff.md) |
| ai-service | 不经过网关 (:8000) | _(Python 服务, 后续补充)_ |

## 四、单体→微服务路径映射

旧单体项目 (端口 :8888) 与新微服务架构 (网关 :8080) 的 URL 对照, 见 [migration-guide.md](migration-guide.md).

## 五、SSE 流式端点

chat-service 有一个 SSE 端点, **不走 Result 包装**, 直接 `text/event-stream`:

- `POST /api/chat/chat/stream/messages` — 流式 AI 对话

详见 [chat-service.md](chat-service.md).
