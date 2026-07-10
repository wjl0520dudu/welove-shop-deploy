# trade-service API

> 网关前缀: `/api/trade` · 鉴权: **全部需登录** (白名单仅 `/internal/**` + `/actuator/**`)

---

## 1. CartController — 购物车

全部需登录.

### POST /api/trade/cart/add — 加入购物车

**Query 参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `productId` | Long | 是 | 商品 ID |
| `skuId` | Long | 否 | SKU ID (不选规格时为空) |
| `quantity` | Integer | 否 | 数量, 默认 1 |

**响应:** `Result<Void>`

---

### DELETE /api/trade/cart/remove — 移除商品 (按 productId)

**Query 参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `productId` | Long | 是 | 商品 ID |
| `quantity` | Integer | 否 | 移除数量 (<=0 或空=全删) |

---

### DELETE /api/trade/cart/removeById — 移除商品 (按 cartItemId)

**Query:** `cartItemId` (Long, 必填)

---

### PUT /api/trade/cart/update — 更新数量

**Query:** `productId` (Long, 必填) · `quantity` (Integer, 必填)

---

### PUT /api/trade/cart/updateSku — 切换 SKU

**Query:** `productId` (Long, 必填) · `oldSkuId` (Long, 可选) · `newSkuId` (Long, 必填)

---

### GET /api/trade/cart/list — 购物车列表

**响应:** `Result<List<CartItemVO>>`

**CartItemVO 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 购物车条目 ID |
| `userId` | Long | |
| `productId` | Long | 商品 ID |
| `skuId` | Long | SKU ID |
| `quantity` | Integer | 数量 |
| `productTitle` | String | 商品标题 (Feign 补) |
| `productImage` | String | 商品主图 (Feign 补) |
| `basePrice` | BigDecimal | 商品基础价 (未选 SKU 时使用) |
| `skuPrice` | BigDecimal | SKU 价格 (选了 SKU 时) |
| `skuProperties` | String | SKU 规格快照, 如 `"容量: 30ml"` |
| `stock` | Integer | SKU 库存 (0 时前端显示"暂时缺货") |
| `productStatus` | Integer | 1=上架, 0=下架 |
| `totalPrice` | BigDecimal | 单项总价 (单价 × 数量) |

---

### GET /api/trade/cart/count — 购物车数量

**响应:** `Result<Long>` — 用户购物车商品种类数.

---

## 2. OrderController — 订单

全部需登录.

### POST /api/trade/order/create — 创建订单

**请求体: `CreateOrderRequest`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `addressId` | Long | 是 | 收货地址 ID |
| `items` | List\<OrderItemDto\> | 是 | 订单明细 |
| `remark` | String | 否 | 订单备注 |
| `receiverName` | String | 否 | 覆盖收货人 (默认取地址里的) |
| `receiverPhone` | String | 否 | 覆盖收货手机号 |

**OrderItemDto:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `productId` | Long | 是 | 商品 ID |
| `skuId` | Long | 否 | SKU ID |
| `quantity` | Integer | 是 | 数量 |

**响应:** `Result<OrderVO>`

**OrderVO 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 订单 ID |
| `orderNo` | String | 订单号 `yyyyMMddHHmmss` + 6 位随机 |
| `userId` | Long | |
| `status` | Integer | 0=待付款, 1=待发货, 2=待收货, 3=已完成, 4=已取消 |
| `totalAmount` | BigDecimal | 订单总金额 |
| `payAmount` | BigDecimal | 实付金额 |
| `freightAmount` | BigDecimal | 运费 |
| `receiverName` | String | 收货人 |
| `receiverPhone` | String | 收货电话 |
| `receiverAddress` | String | 收货地址 (省市区 + 详细) |
| `remark` | String | 备注 |
| `items` | List\<OrderItem\> | **订单明细** (快照字段, 见下表) |
| `createTime` | LocalDateTime | 下单时间 |
| `payTime` | LocalDateTime | 支付时间 |
| `deliveryTime` | LocalDateTime | 发货时间 |
| `receiveTime` | LocalDateTime | 收货时间 |

**OrderItem 对象 (快照冻结):**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 明细 ID |
| `productId` | Long | 商品 ID |
| `productTitle` | String | 快照: 下单时商品标题 |
| `productImage` | String | 快照: 下单时商品图 |
| `skuId` | Long | SKU ID |
| `skuProperties` | String | 快照: SKU 规格 |
| `price` | BigDecimal | 快照单价 |
| `quantity` | Integer | 数量 |
| `totalAmount` | BigDecimal | price × quantity |

> 下单时冻结所有快照字段; 后续商品改价/下架不影响订单历史.

---

### GET /api/trade/order/list — 订单列表 (分页)

**Query 参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `status` | Integer | 否 | — | 状态筛选 |
| `page` | int | 否 | 1 | 页码 |
| `size` | int | 否 | 10 | 每页条数 |

**响应:** `Result<IPage<OrderVO>>`

---

### GET /api/trade/order/{id} — 订单详情

**Path:** `id` (Long) — 订单 ID

**响应:** `Result<OrderVO>`

---

### PUT /api/trade/order/{id}/pay — 标记支付

| 属性 | 值 |
|------|-----|
| Path | `id` (Long) |
| 说明 | 骨架期模拟支付, 状态 0→1 |

---

### PUT /api/trade/order/{id}/cancel — 取消订单

| 属性 | 值 |
|------|-----|
| Path | `id` (Long) |
| 说明 | 状态 → 4 (已取消) |

---

### PUT /api/trade/order/{id}/receive — 确认收货

| 属性 | 值 |
|------|-----|
| Path | `id` (Long) |
| 说明 | 状态 2→3 (已完成) |

---

### DELETE /api/trade/order/{id} — 删除订单

| 属性 | 值 |
|------|-----|
| Path | `id` (Long) |
| 说明 | 仅允许状态 3 (已完成) 或 4 (已取消) 的订单删除 |

---

## 3. 内部端点 (前端不调用)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/internal/order/count` | admin-bff Dashboard |
| GET | `/internal/order/today-revenue` | admin-bff Dashboard |
