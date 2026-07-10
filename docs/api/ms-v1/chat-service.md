# chat-service API

> 网关前缀: `/api/chat` · 鉴权: 除 `/notice/latest` 外全部需登录

---

## 1. ChatController — 对话

### POST /api/chat/chat/conversations — 创建对话

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**Query:** `title` (String, 可选, 默认 `"New Chat"`)

**响应:** `Result<Conversation>`

**Conversation 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 对话 ID |
| `userId` | Long | |
| `title` | String | 对话标题 |
| `scene` | String | 场景 |
| `isPinned` | Boolean/Integer | 是否置顶 |
| `createTime` | LocalDateTime | |
| `updateTime` | LocalDateTime | |
| `messageCount` | Integer | 消息数 (非持久, 查询时计算) |

---

### GET /api/chat/chat/conversations — 对话列表

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**响应:** `Result<List<Conversation>>` — 当前用户所有对话.

---

### POST /api/chat/chat/messages — 发送消息 (非流式)

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**请求体: `ChatRequest`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `userId` | Long | 是 | 用户 ID |
| `conversationId` | Long | 是 | 对话 ID |
| `content` | String | 是 | 消息内容 |

**响应:** `Result<Message>`

**Message 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 消息 ID |
| `conversationId` | Long | |
| `role` | String | `"user"` \| `"assistant"` |
| `content` | String | 消息正文 |
| `messageType` | String | 消息类型 |
| `productCards` | List\<Map\> | **JSONB** — AI 推荐商品卡片 |
| `confirmCard` | Map | **JSONB** — 确认卡片 |
| `cartSelection` | Map | **JSONB** — 购物车选择 |
| `imageUrl` | String | 图片 URL |
| `sources` | String | 引用来源 |
| `taskType` | String | AI 任务类型 |
| `feedbackType` | String | 用户反馈类型 |
| `feedbackTime` | LocalDateTime | |
| `createTime` | LocalDateTime | |

---

### POST /api/chat/chat/stream/messages — 流式对话 (SSE)

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |
| Content-Type | `text/event-stream` |
| 特殊 | **不走 Result 包装** |

**请求体: `StreamChatRequest`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `userId` | Long | 是 | |
| `conversationId` | Long | 是 | |
| `content` | String | 是 | 用户消息 |
| `username` | String | 否 | 用户名 (默认 `"user"`) |
| `isAdmin` | boolean | 否 | 是否管理员 |
| `gender` | String | 否 | 性别 |
| `skinType` | String | 否 | 肤质 |
| `preferenceTags` | List\<String\> | 否 | 偏好标签 |

**响应格式:** SSE 事件流

```
event: message
data: {"content": "你好", ...}

event: product_card
data: {"product_id": 12, "title": "修复面霜", ...}

event: done
data: {"messageId": 42}
```

> 实时推送, 无需轮询. 后端通过 WebClient 订阅 Python ai-service `/ask/stream` 再转发.
> SseEmitter 超时: 5 分钟.

---

### GET /api/chat/chat/messages — 获取对话消息

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**Query:** `conversationId` (Long, 必填)

**响应:** `Result<List<Message>>`

---

### DELETE /api/chat/chat/conversations/{id} — 删除对话

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**Path:** `id` (Long)

---

### PUT /api/chat/chat/conversations/{id} — 更新对话

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**Path:** `id` (Long) · **Query:** `title` (String, 可选) · `isPinned` (Boolean, 可选)

---

### POST /api/chat/chat/messages/feedback — 消息反馈

| 属性 | 值 |
|------|-----|
| 鉴权 | **是** |

**请求体: `FeedbackRequest`**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `messageId` | Long | 是 | |
| `feedbackType` | String | 是 | 如 `"like"` / `"dislike"` |

---

## 2. AgentController — Agent 运行追踪

全部需登录.

### POST /api/chat/agent/run — 启动 Agent 运行

**请求体: `AgentRunRequest`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `runId` | String | Agent 运行 ID |
| `traceId` | String | 分布式追踪 ID |
| `conversationId` | String | 关联对话 |
| `userId` | String | 用户 |
| `input` | String | 用户输入 |
| `goal` | String | Agent 目标 |
| `agentType` | String | Agent 类型 |
| `context` | String | 附加上下文 |
| `isAdmin` | Boolean | 是否管理员 |

**响应:** `Result<AgentRunResponse>` — 含完整 steps, toolCalls, sources.

---

### GET /api/chat/agent/runs — Agent 运行列表

**Query:** `pageNum` (int, 默认 1) · `pageSize` (int, 默认 20) · `status` (String, 可选)

### GET /api/chat/agent/run/{runId} — 运行详情

**Path:** `runId` (String)

### DELETE /api/chat/agent/run/{runId} — 删除运行

**Path:** `runId` (String)

---

## 3. KnowledgeController — 知识库

全部需登录.

### POST /api/chat/knowledge/upload — 上传知识文档

| 属性 | 值 |
|------|-----|
| Content-Type | `multipart/form-data` |

**Form 字段:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | MultipartFile | 是 | 文档文件 |
| `categoryId` | Long | 是 | 分类 ID |

**响应:** `Result<KnowledgeDoc>`

---

### GET /api/chat/knowledge/list — 知识文档列表

**Query:** `categoryId` (Long, 可选)

**响应:** `Result<List<KnowledgeDoc>>`

**KnowledgeDoc 对象:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | |
| `docName` | String | 文档名 |
| `filePath` | String | 文件路径 |
| `categoryId` | Long | |
| `docType` | String | 文件类型 (扩展名) |
| `status` | Integer | 处理状态 |
| `createTime` | LocalDateTime | |

---

### DELETE /api/chat/knowledge/{id} — 删除知识文档

**Path:** `id` (Long)

---

## 4. NoticeController — 公告

### GET /api/chat/notice/latest — 最新公告

| 属性 | 值 |
|------|-----|
| 鉴权 | **否** (公开) |

**响应:** `Result<List<Notice>>`

---

## 5. 内部端点 (前端不调用)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/internal/conversation/count` | admin-bff Dashboard |
