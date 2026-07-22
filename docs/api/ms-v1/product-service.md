# product-service API

> 网关前缀: `/api/product` · 鉴权: 浏览类 GET 匿名, 写操作 (评价/推荐日志) 需 JWT

---

## 1. ProductController — 商品

### GET /api/product/product/list — 商品列表 (分页)

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

**Query 参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `categoryId` | Long | 否 | — | 分类筛选 |
| `page` | int | 否 | 1 | 页码 |
| `size` | int | 否 | 20 | 每页条数 |
| `sortBy` | String | 否 | `"sales"` | 排序字段 |
| `sortOrder` | String | 否 | `"desc"` | 排序方向 |

**响应:** `Result<IPage<Product>>`

**Product 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 商品 ID |
| `productCode` | String | 商品编码, 如 `p_beauty_001` |
| `categoryId` | Long | 分类 ID |
| `title` | String | 商品标题 |
| `brand` | String | 品牌 |
| `subCategory` | String | 子分类 |
| `basePrice` | BigDecimal | 基础价格 |
| `imageUrl` | String | 主图 URL (相对路径, 前端拼 CDN) |
| `description` | String | 商品描述 (长文本) |
| `tags` | String | 标签 (逗号分隔) |
| `rating` | BigDecimal | 评分 0-5 |
| `reviewCount` | Integer | 评价数 |
| `salesCount` | Integer | 销量 |
| `status` | Integer | 1=上架, 0=下架 |

---

### GET /api/product/product/search — 商品搜索

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

**Query 参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keyword` | String | 是 | — | 搜索关键词 |
| `limit` | int | 否 | 20 | 返回条数 |

**响应:** `Result<List<Product>>`

> 搜索支持同义词扩展 (16 组: "干皮→干性肌肤", "防晒→隔离" 等) + 相关性打分.

---

### GET /api/product/product/hot — 热销商品

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

**Query 参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `limit` | int | 否 | 10 | 返回条数 |

**响应:** `Result<List<Product>>` — 按销量倒序.

---

### GET /api/product/product/{id} — 商品详情 (聚合)

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

**Path:** `id` (Long) — 商品 ID

**响应:** `Result<ProductDetailVO>`

**ProductDetailVO 结构:**

```json
{
  "code": 0,
  "data": {
    "product": { ... },       // Product 对象
    "skus": [                 // SKU 列表
      {
        "id": 1,
        "productId": 1,
        "skuCode": "sku_001",
        "properties": { "容量": "30ml" },
        "price": 260.00,
        "stock": 100,
        "isDefault": 1
      }
    ],
    "images": [               // 图片列表
      { "id": 1, "imageUrl": "/img/p1.jpg", "imageType": "main", "sortOrder": 1 }
    ],
    "faqs": [                 // FAQ 列表
      { "id": 1, "question": "适合什么肤质?", "answer": "干皮最合适" }
    ],
    "reviews": [              // 评价列表 (top N)
      { "id": 1, "nickname": "用户A", "rating": 4, "content": "好用", "isAnonymous": 0 }
    ]
  }
}
```

**ProductSku 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | SKU ID |
| `productId` | Long | 商品 ID |
| `skuCode` | String | SKU 编码 |
| `properties` | Map\<String,String\> | 规格键值, 如 `{"容量":"30ml"}` |
| `price` | BigDecimal | SKU 价格 |
| `stock` | Integer | 库存 |
| `isDefault` | Integer | 1=默认规格 |

---

### GET /api/product/product/batch — 批量查商品

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** (内部 Feign 用) |

**Query:** `ids` (List\<Long\>, 必填) — 逗号分隔

**响应:** `Result<List<Product>>`

---

## 2. ProductResourceController — 商品资源

### GET /api/product/product/{id}/skus — SKU 列表

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

**Path:** `id` (Long)

**响应:** `Result<List<ProductSku>>`

### GET /api/product/product/{id}/images — 图片列表

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

### GET /api/product/product/{id}/faqs — FAQ 列表

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

### POST /api/product/product/{id}/reviews — 提交评价

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**Path:** `id` (Long) — 商品 ID

**请求体: `ProductReview`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `rating` | Integer | 是 | 1-5 星 |
| `content` | String | 是 | 评价内容 |
| `nickname` | String | 否 | 展示昵称 |
| `isAnonymous` | Integer | 否 | 1=匿名 |

**响应:** `Result<ProductReview>`

---

## 3. CategoryController — 分类

### GET /api/product/category/list — 分类列表

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

**响应:** `Result<List<Category>>`

**Category 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 分类 ID |
| `name` | String | 分类名 |
| `description` | String | 分类描述 |
| `iconUrl` | String | 图标 URL |
| `sortOrder` | Integer | 排序权重 |
| `isActive` | Integer | 1=启用 |

### GET /api/product/category/{id} — 分类详情

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** |

---

## 4. RecommendationLogController — 推荐日志

全部需登录. 由 chat-service / 前端埋点调用.

### POST /api/product/recommend-log — 记录推荐

**请求体:** `RecommendationLog` (含 `sessionId`, `recommendedProductIds`, `recommendReason` 等)

### PUT /api/product/recommend-log/{id}/click — 用户点击推荐

**Path:** `id` (Long) — 推荐日志 ID

### PUT /api/product/recommend-log/{id}/feedback?value=0|1 — 用户反馈

**Path:** `id` (Long) · **Query:** `value` (Integer, 0=不满意, 1=满意)

---

## 5. 内部端点 (前端不调用)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/internal/product/count` | admin-bff Dashboard 用 |
