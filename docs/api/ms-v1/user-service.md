# user-service API

> 网关前缀: `/api/user` · 鉴权机制: JWT (HS256) · 白名单: `/auth/sendCode`, `/auth/login`, `/auth/refresh`

---

## 1. AuthController — 认证

### POST /api/user/auth/sendCode — 发送短信验证码

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |
| 请求方式 | Query String (form-urlencoded 亦可) |

**Query 参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phone` | String | 是 | 11 位手机号 |

**响应:** `Result<String>` — data 为 `"验证码已发送"`

```json
{ "code": 0, "message": "success", "data": "验证码已发送" }
```

> 骨架期验证码为 mock (固定 `000000`), 直接显示在日志里.

---

### POST /api/user/auth/login — 手机号验证码登录

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |
| Content-Type | `application/json` |

**请求体: `LoginRequest`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phone` | String | 是 | 11 位手机号 |
| `code` | String | 是 | 短信验证码 |
| `password` | String | 否 | 密码登录字段 (骨架期不启用) |

**响应:** `Result<Map<String, Object>>`

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "token": "eyJhbG...",
    "refreshToken": "eyJhbG...",
    "user": {
      "id": 1,
      "username": "用户_138****0001",
      "phone": "13812340001",
      "avatarUrl": null,
      "gender": 0,
      "ageRange": null,
      "skinType": null,
      "preferenceTags": null,
      "status": 1,
      "createTime": "2026-07-09T12:00:00",
      "updateTime": "2026-07-09T12:00:00"
    }
  }
}
```

> **新用户自动注册**: 首次登录的手机号自动创建 `user` 记录.

---

### POST /api/user/auth/refresh — 刷新 access token

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** (用 refresh token 认证) |
| Header | `Authorization: Bearer <refreshToken>` |

**请求体:** 无

**响应:** `Result<Map<String, Object>>` — 同 login, 返回新 token + 新 refreshToken + user.

---

### GET /api/user/auth/profile — 获取当前用户信息

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |
| Header | `Authorization: Bearer <token>` |

**响应:** `Result<User>`

**User 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 用户 ID |
| `username` | String | 用户名 |
| `phone` | String | 手机号 |
| `avatarUrl` | String | 头像 URL |
| `gender` | Integer | 0=未知, 1=男, 2=女 |
| `ageRange` | String | 年龄段, 如 `"18-24"` |
| `skinType` | String | 肤质, 如 `"干皮"` |
| `preferenceTags` | List\<String\> | 偏好标签 |
| `status` | Integer | 1=正常, 0=禁用 |
| `createTime` | LocalDateTime | |
| `updateTime` | LocalDateTime | |

> `password` 字段被 `@JsonIgnore` 排除, 不会出现在响应中.

---

### POST /api/user/auth/update — 更新用户资料

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**请求体: `UpdateUserRequest`** (所有字段均可空, 仅非空字段被更新)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `userId` | Long | **忽略** | Controller 从 JWT 覆盖, 防止越权 |
| `username` | String | 否 | 用户名 |
| `password` | String | 否 | 新密码 (空则不修改) |
| `avatarUrl` | String | 否 | 头像 URL |
| `gender` | Integer | 否 | 0=未知, 1=男, 2=女 |
| `ageRange` | String | 否 | 年龄段 |
| `skinType` | String | 否 | 肤质 |
| `preferenceTags` | List\<String\> | 否 | 偏好标签 |

**响应:** `Result<User>` — 更新后的用户信息.

---

## 2. AddressController — 收货地址

全部需登录.

### GET /api/user/address/list — 地址列表

**响应:** `Result<List<Address>>`

**Address 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 地址 ID |
| `userId` | Long | 用户 ID |
| `receiverName` | String | 收货人 |
| `phone` | String | 手机号 |
| `province` | String | 省 |
| `city` | String | 市 |
| `district` | String | 区 |
| `detail` | String | 详细地址 |
| `isDefault` | Integer | 1=默认, 0=非默认 |
| `createTime` | LocalDateTime | |
| `updateTime` | LocalDateTime | |

### POST /api/user/address/add — 新增地址

**请求体:** Address (JSON, `userId` 由 Controller 从 JWT 覆盖)

### PUT /api/user/address/update — 更新地址

**请求体:** Address (JSON, 需含 `id`)

### DELETE /api/user/address/delete?id={id} — 删除地址

**Query:** `id` (Long, 必填)

### PUT /api/user/address/setDefault?id={id} — 设默认地址

**Query:** `id` (Long, 必填)

---

## 3. UserFavoriteController — 收藏

全部需登录.

### POST /api/user/favorites/{productId} — 添加收藏 (幂等)

**Path:** `productId` (Long)

### DELETE /api/user/favorites/{productId} — 取消收藏

**Path:** `productId` (Long)

### GET /api/user/favorites — 收藏列表

**响应:** `Result<List<UserFavorite>>`

**UserFavorite 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | |
| `userId` | Long | |
| `productId` | Long | |
| `createTime` | LocalDateTime | |
| `productName` | String | 骨架期为空 (TODO Feign 补齐) |
| `productImage` | String | 骨架期为空 |
| `productPrice` | BigDecimal | 骨架期为空 |

---

## 4. UserBrowseHistoryController — 浏览历史

全部需登录.

### POST /api/user/browse-history — 上报浏览记录

**请求体: `UserBrowseHistory`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `productId` | Long | 是 | 浏览商品 ID |
| `source` | String | 否 | 来源: "推荐"/"搜索"/"详情页" |
| `durationSec` | Integer | 否 | 停留时长 (秒) |

> `userId` 由 Controller 从 JWT 覆盖. 同一 (userId, productId) 为 upsert, 刷新记录时间.

### GET /api/user/browse-history — 历史列表

**响应:** `Result<List<UserBrowseHistory>>` (按时间倒序)

### DELETE /api/user/browse-history/{historyId} — 删除某条记录

**Path:** `historyId` (Long)

---

## 5. 内部端点 (前端不调用)

供微服务间 Feign 调用, 不经过网关. 前端忽略.

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/internal/user/count` | admin-bff Dashboard 用 |
| GET | `/internal/address/{id}` | trade-service 下单查地址 |
