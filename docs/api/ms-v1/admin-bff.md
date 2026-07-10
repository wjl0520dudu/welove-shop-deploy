# admin-bff API

> 网关前缀: `/api/admin` · 鉴权: `/login` 免鉴权, 其他需 role=ADMIN 的 JWT

---

## 1. AdminController — 管理员认证

### POST /api/admin/login — 管理员登录

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

**请求体: `LoginRequest`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | String | 是 | 管理员用户名 |
| `password` | String | 是 | 密码 |

**响应:** `Result<Map<String, Object>>`

```json
{
  "code": 0,
  "data": {
    "token": "eyJhbG...",
    "refreshToken": "eyJhbG...",
    "user": {
      "id": 1,
      "username": "admin",
      "role": "ADMIN"
    }
  }
}
```

> 骨架期默认管理员: `admin` / `admin123`
> 密码首次用明文登录后自动升级为 BCrypt 存储.

---

## 2. DashboardController — 首页统计

### GET /api/admin/dashboard/stats — Dashboard 数据

| 属性 | 值 |
|------|-----|
| 鉴权 | **是 (role=ADMIN)** |
| 说明 | Feign 聚合 4 个下游服务的 count 接口 |

**响应:** `Result<DashboardStats>`

**DashboardStats 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `userCount` | Long | 注册用户总数 |
| `productCount` | Long | 商品总数 |
| `orderCount` | Long | 订单总数 |
| `conversationCount` | Long | 对话总数 |
| `todayRevenue` | BigDecimal | 今日营收 |

```json
{
  "code": 0,
  "data": {
    "userCount": 128,
    "productCount": 100,
    "orderCount": 35,
    "conversationCount": 12,
    "todayRevenue": 5999.50
  }
}
```

---

## 错误码

| code | 含义 |
|------|------|
| 60001 | 用户名或密码错误 |
| 60003 | 非管理员 token (JWT claims.role ≠ "ADMIN") |
