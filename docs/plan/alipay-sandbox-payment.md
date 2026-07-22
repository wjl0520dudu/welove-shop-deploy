# 支付宝沙箱支付接入文档

> **状态**：代码已落地 ✅（2026-07-20，提交 `61c2498 feat(payment): add sandbox Alipay payment flow`）
> **范围**：trade-service 后端 + 前端 H5 接入 + 内网穿透方案
> **依赖**：Spring Boot 3.2.5 + Alipay EasySDK 2.2.2 + 沙箱 APPID

---

## 1. 背景与目标

电商业务的支付闭环需要可演示的端到端流程。支付宝沙箱（sandbox）提供"无需真实资金"的测试环境，适合：

- 前端 / 客户端联调支付流程
- 后端验证异步通知 + 签名
- 演示项目功能

**目标**：用户在下单后能体验完整"唤起支付 → 输入密码 → 回到成功页"的链路。

---

## 2. 整体架构

```
┌─────────────┐                ┌─────────────────┐                ┌──────────────────┐
│   浏览器    │                │   trade-service │                │   支付宝沙箱      │
│  (H5/PC)    │                │   :8083         │                │  openapi-sandbox │
└──────┬──────┘                └────────┬────────┘                └────────┬─────────┘
       │                               │                                  │
       │  1. POST /alipay/create/{id}  │                                  │
       │     (返回 form HTML)          │                                  │
       ├──────────────────────────────►│                                  │
       │                               │                                  │
       │  2. 浏览器自动提交 form       │                                  │
       │  ──────────────────────────────►│  (跳到支付宝收银台)              │
       │                                                              ────►│
       │                                                              ◄────┤
       │  3. 用户输入密码付款                                            │
       │                                                              ────►│
       │                                                              ◄────┤
       │                               │                                  │
       │  4a. 浏览器同步跳到 returnUrl  │                                  │
       │  ◄──────────────────────────────                                 │
       │                               │                                  │
       │  4b. 支付宝服务器异步 POST     │                                  │
       │      notifyUrl               ◄────────────────────────────  ────│
       │                               │  (验签 + 改订单状态)            │
       │  5. 后端返回 "success"        │                                  │
       ├──────────────────────────────►│  ──────────────────────────────►│
       │                               │                                  │
       │  6. 浏览器轮询 /alipay/status  │                                  │
       │     (前端支付结果页发起)        │                                  │
       ├──────────────────────────────►│                                  │
       │                               │                                  │
       │  7. 显示支付成功 / 失败         │                                  │
       │  ◄──────────────────────────────                                 │
```

---

## 3. 服务端架构（trade-service）

### 3.1 模块分层

| 层 | 类 | 职责 |
|---|---|---|
| Controller | `AlipayController` | 用户端 3 个接口（create / status / close）|
| Controller | `AlipayNotifyController` | 支付宝回调 2 个接口（notify / return）|
| Service | `PaymentService` + Impl | 支付核心逻辑：生成支付页 / 处理通知 / 查询状态 / 关闭 |
| Config | `AlipayProperties` | 绑 `alipay.*` 配置段（@ConfigurationProperties）|
| Config | `AlipayConfig` | @PostConstruct 初始化 EasySDK（Factory.setOptions）|
| Entity | `Order` | 加 `payChannel` + `tradeNo` 字段 |
| DTO | `PayStatusVO` | 暴露给前端的支付状态 |
| Exception | `TradeErrorCode` | 加 40301~40305 支付错误码 |

### 3.2 API 列表

#### POST `/alipay/create/{orderId}`

| 项 | 值 |
|---|---|
| 鉴权 | 需要登录（userId 通过 JWT）|
| 返回 | `text/html` — 支付宝收银台 form HTML |
| 业务逻辑 | 校验订单归属 + 调用 EasySDK 生成 form |

#### GET `/alipay/status/{orderId}`

| 项 | 值 |
|---|---|
| 鉴权 | 需要登录 |
| 返回 | `Result<PayStatusVO>` |
| 字段 | `orderNo / orderStatus / tradeNo / tradeStatus / payAmount / payChannel` |
| 业务逻辑 | 沙箱启用时主动调支付宝 query，沙箱关闭时直接查本地订单 |

#### POST `/alipay/close/{orderId}`

| 项 | 值 |
|---|---|
| 鉴权 | 需要登录 |
| 业务逻辑 | 调支付宝 close + 本地订单状态置为已取消 |

#### POST `/alipay/notify` ⭐ 异步通知

| 项 | 值 |
|---|---|
| 鉴权 | **白名单**（无 JWT）|
| 请求 | 支付宝服务器 POST，form 表单（out_trade_no / trade_no / total_amount / sign）|
| 响应 | **必须纯字符串** `"success"` 或 `"fail"`，**不能含 HTML/JSON/换行/BOM** |
| 业务逻辑 | EasySDK verifyNotify 验签 + 金额校验 + 幂等更新订单状态（仅 status=0 时）|
| 错误码 | `40302 PAY_NOTIFY_INVALID`（验签失败 / 金额不一致 / out_trade_no 缺失）|

#### GET `/alipay/return` 同步跳转

| 项 | 值 |
|---|---|
| 鉴权 | **白名单** |
| 业务逻辑 | 仅做页面展示，**不修改订单状态**（业务以 notify 为准）|
| 默认返回 | 纯字符串"支付完成,请回到订单列表查看状态" |

### 3.3 双路径设计（沙箱 vs 本地）

```java
if (alipayProperties.isEnabled()) {
    // 真沙箱：调 EasySDK 生成 form / 处理 notify
    return Factory.Payment.Page().asyncNotify(notifyUrl).pay(...);
} else {
    // 本地 mock：直接 mock 改成已支付,返回 "支付成功" 字符串
    orderService.markPaidByCallback(orderNo, "MOCK-" + UUID, amount, "MOCK");
    return "<h1>模拟支付成功</h1>...";
}
```

**好处**：本地开发不配沙箱也能跑通流程；测试 / 生产 / 沙箱切换只改一个 `enabled` 开关。

### 3.4 幂等性

`markPaidByCallback` 三层防御：

1. **out_trade_no 不存在** → 抛 `ORDER_NOT_FOUND`
2. **金额不一致** → 抛 `PAY_NOTIFY_INVALID`
3. **已支付订单** → 静默返回（不抛错）

支付宝的异步通知最多重试 4 次（24h），幂等性是必须的。

---

## 4. 配置（application.yml）

### 4.1 application.yml 模板

```yaml
alipay:
  enabled: ${ALIPAY_ENABLED:false}                       # 默认关闭,本地用 mock
  app-id: ${ALIPAY_APP_ID:2021000123456789}              # 沙箱默认 APPID
  app-private-key: ${ALIPAY_APP_PRIVATE_KEY:}            # PKCS8 格式,无 BEGIN/END
  alipay-public-key: ${ALIPAY_ALIPAY_PUBLIC_KEY:}        # ⚠ 支付宝公钥,不是应用公钥
  gateway-url: ${ALIPAY_GATEWAY:https://openapi.alipaydev.com/gateway.do}
  protocol: https
  sign-type: RSA2
  charset: UTF-8
  notify-url: ${ALIPAY_NOTIFY_URL:http://localhost:8083/alipay/notify}
  return-url: ${ALIPAY_RETURN_URL:http://localhost:8083/alipay/return}
```

### 4.2 application-dev.yml（沙箱调试）

```yaml
alipay:
  enabled: ${ALIPAY_ENABLED:true}
  app-id: ${ALIPAY_APP_ID:2021000123456789}
  app-private-key: ${ALIPAY_APP_PRIVATE_KEY:MIIEvQIBA...}    # 真实私钥(不进 git)
  alipay-public-key: ${ALIPAY_ALIPAY_PUBLIC_KEY:MIIBIjANB...} # 真实公钥(不进 git)
  gateway-url: ${ALIPAY_GATEWAY:https://openapi.alipaydev.com/gateway.do}
  notify-url: ${ALIPAY_NOTIFY_URL:https://你的公网域名/api/trade/alipay/notify}
  return-url: ${ALIPAY_RETURN_URL:https://你的公网域名/alipay/return}
```

### 4.3 密钥获取方式

| 密钥 | 来源 | 路径 |
|---|---|---|
| 应用私钥 | 自己生成 | `openssl genrsa -out app_private_key.pem 2048` |
| 应用公钥 | 私钥推导 | `openssl rsa -in app_private_key.pem -pubout -out app_public_key.pem` |
| **支付宝公钥** | 沙箱/生产后台 | https://open.alipay.com/develop/sandbox/account → 应用信息 → 加密方式(RSA2) → 查看支付宝公钥 |
| APPID | 沙箱/生产后台 | 同上，应用信息卡片顶部 |

⚠ **关键区别**：`alipay-public-key` 是 **支付宝公钥**（支付宝给你验签用的），**不是你的应用公钥**。填错会导致验签失败。

---

## 5. 数据库迁移（Flyway V2）

[services/trade-service/src/main/resources/db/migration/V2__add_payment_columns_to_orders.sql](../../services/trade-service/src/main/resources/db/migration/V2__add_payment_columns_to_orders.sql)：

```sql
SET search_path TO trade_svc;
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS pay_channel VARCHAR(20) NOT NULL DEFAULT 'MOCK',
    ADD COLUMN IF NOT EXISTS trade_no    VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_trade_no
    ON orders(trade_no) WHERE trade_no IS NOT NULL;
```

- `pay_channel`：`MOCK`（本地 mock）/ `ALIPAY_SANDBOX`（沙箱）/ `ALIPAY`（生产）
- `trade_no`：支付宝交易号（异步通知时写入）
- **部分唯一索引**：`trade_no IS NOT NULL` 时才去重（mock 订单无 trade_no 不影响）

---

## 6. 异步通知链路 + 内网穿透

### 6.1 为什么需要内网穿透

支付宝服务器**主动** POST 到你的 `notify-url`。如果 trade-service 跑在你本地 Windows 上（无公网 IP），支付宝服务器无法访问。

**方案**：

```
┌──────────────┐         ┌────────────┐         ┌──────────────────┐
│  支付宝服务器  │  HTTPS  │  云服务器    │  HTTP   │  本地 trade-service│
│  openapi..   ├────────►│  frps :443 ├────────►│  :8083 (Windows)  │
└──────────────┘         └────────────┘         └──────────────────┘
                          (腾讯云 Ubuntu)
```

- **frp**（frps 服务端 + frpc 客户端）：把本地端口暴露到公网
- 域名（可选）：frps 直接用 IP 也行（沙箱支持 HTTP）
- 证书（必填 HTTPS）：frps 用自签证书（沙箱不严格校验）或 Let's Encrypt

### 6.2 frps.toml 关键配置

```toml
bindPort = 7000

# 关键：HTTP virtual host
vhostHTTPPort = 80
vhostHTTPSPort = 443

# 强制 HTTPS（让所有 HTTP 流量跳到 HTTPS）
[[httpsPlugins]]
type = "https2http"
localAddr = "127.0.0.1:8083"  # trade-service 实际端口
crtPath = "/path/to/server.crt"
keyPath = "/path/to/server.key"
hostRewrite = "你的域名"

# TOML 不支持单位后缀
transport.maxBandwidthPerProxy = 10485760  # 10MB(不是 10MB,会报错)
```

### 6.3 frpc.toml

```toml
serverAddr = "x.x.x.x"
serverPort = 7000
auth.token = "your-token"

[[proxies]]
name = "trade-service"
type = "https"
localIP = "127.0.0.1"
localPort = 8083
customDomains = ["pay-dev.example.com"]
```

### 6.4 notify-url 和 return-url 该填什么

| 字段 | 填什么 | 备注 |
|---|---|---|
| **notify-url** | `https://你的公网域名/api/trade/alipay/notify`（经 gateway）或 `https://公网IP/alipay/notify`（直连 frp） | 支付宝服务器要能 POST 通 |
| **return-url** | `https://你的公网域名/alipay/return` | 浏览器要能 GET 通（用户付款后跳转）|

⚠ **必须注意**：

- 控制台的"授权回调地址" = `return-url`，**不接受 notify-url**
- notify-url 由 `Factory.Payment.Page().asyncNotify(notifyUrl)` 链式设置，**不进控制台**
- 控制台和代码的 return-url 必须一致，否则浏览器跳错

### 6.5 生产环境怎么走

生产**不需要 frp**：

```
┌──────────────┐         ┌────────────┐         ┌──────────────────┐
│  支付宝服务器  │  HTTPS  │  Nginx      │  HTTP   │  trade-service    │
│  openapi..   ├────────►│  :443      ├────────►│  :8083            │
└──────────────┘         │  (证书)    │         └──────────────────┘
                         └────────────┘
```

直接部署 trade-service 到云服务器 + Nginx 反代 + 真证书 + 真实域名。notify-url 用 `https://www.yourdomain.com/api/trade/alipay/notify`。

---

## 7. 前端集成（H5）

### 7.1 API 模块（[web/welove-shop/src/api/payment.js](../../web/welove-shop/src/api/payment.js)）

```js
export function createAlipayForm(orderId) {
  return request({
    url: `/api/trade/alipay/create/${orderId}`,
    method: 'POST',
    responseType: 'text'   // ← 关键,后端返回 HTML 不要按 JSON 解析
  });
}

export function getPayStatus(orderId) {
  return request({ url: `/api/trade/alipay/status/${orderId}`, method: 'GET' });
}

export function closePay(orderId) {
  return request({ url: `/api/trade/alipay/close/${orderId}`, method: 'POST' });
}
```

### 7.2 "立即支付"按钮（order-detail.vue）

```javascript
async pay() {
  const html = await createAlipayForm(this.id);
  // 关键: 浏览器对 innerHTML 注入的 <script> 默认不执行(CSP)
  // 必须用 DOMParser 解析 + 手动创建 form 提交
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  const form = doc.querySelector('form');
  if (!form) return;
  const liveForm = document.createElement('form');
  liveForm.method = form.method;
  liveForm.action = form.action;
  // ... 复制 input, 然后 liveForm.submit()
}
```

### 7.3 支付结果页（payment/result.vue）

轮询 `/alipay/status/{orderId}` 直到 status ≠ 0，显示对应状态卡片（loading / success / failed / closed）。

```javascript
async pollOnce() {
  const data = await getPayStatus(this.orderId);
  this.applyStatus(data);
  // 终态停止轮询
  if (['success', 'failed', 'closed'].includes(this.state)) {
    this.stopPoll();
  }
}
```

---

## 8. 端到端调试步骤

### 8.1 准备阶段

```
1. 启 Nacos（127.0.0.1:8848）
2. 启 PostgreSQL（127.0.0.1:5432 / welove_shop_search）
3. 启 Redis（127.0.0.1:6379）
4. 启 trade-service（mvn spring-boot:run）
5. 启 frps + frpc（或用 ngrok 暴露本地 8083）
```

### 8.2 配置检查

```
[ ] application-dev.yml 的 alipay.enabled = true
[ ] APPID 是沙箱默认 2021000123456789
[ ] app-private-key 和 alipay-public-key 都填了
[ ] gateway-url 是 https://openapi.alipaydev.com/gateway.do
[ ] notify-url 用 frp 公网地址
[ ] 支付宝控制台"授权回调地址" = return-url (不是 notify-url)
```

### 8.3 端到端测试

```
1. 创建订单（用真实手机号登录）
2. POST /alipay/create/{orderId} → 拿到 HTML form
3. 浏览器打开 form.html → 自动跳到支付宝沙箱收银台
4. 用沙箱买家账号登录（控制台 https://open.alipay.com/develop/sandbox/account 看）
5. 付款成功 → 浏览器跳到 return-url → 看到支付结果页
6. 轮询 status 接口 → 看到状态变成已支付
7. 数据库验证：
   SELECT status, pay_channel, trade_no FROM trade_svc.orders WHERE id={orderId};
   应该 status=1, pay_channel='ALIPAY_SANDBOX', trade_no='2026xxx...'
```

### 8.4 异步通知调试

```
1. trade-service 控制台看：[alipay-notify] handle error / order paid
2. 成功日志: [order-callback] order paid, orderNo=xxx, tradeNo=xxx
3. 失败日志: [order-callback] amount mismatch / verifyNotify failed
4. frpc 日志：看有没有来自 140.205.94.189 的 POST /alipay/notify
```

---

## 9. 常见错误及排查

### 9.1 "EasySDK Config 不含 charset 字段"

**原因**：旧文档示例设 `config.charset = "UTF-8"`，EasySDK 2.x Config 类没这个字段。

**解决**：直接删掉这行，EasySDK 内部默认 UTF-8。

### 9.2 "异步通知验签失败"

**原因**：99% 是 `alipay-public-key` 填错了——填成了"应用公钥"而不是"支付宝公钥"。

**解决**：去控制台"应用信息 → 加密方式(RSA2) → 查看支付宝公钥"重新拷贝。

### 9.3 "金额不一致"

**原因**：订单金额小数位 / 精度不匹配。

**解决**：
- 数据库金额用 `DECIMAL(10,2)` 存
- 传给支付宝时用 `.toString()` 不要 `.toPlainString()`（保留精度）
- 异步通知拿到的 `total_amount` 是字符串，直接 `new BigDecimal(totalAmount).compareTo(...)`

### 9.4 "异步通知一直重试"

**原因**：返回内容不是纯字符串 `"success"` —— 包含了 HTML / JSON / 换行 / BOM。

**解决**：
- 返回类型必须是 `String`，不能返回 `Result.ok()`
- 不能用 `@RestControllerAdvice` 包装（会加 JSON 包装）
- 检查响应头 `Content-Type: text/plain`

### 9.5 "浏览器点立即支付没反应"

**原因**：现代浏览器对 `innerHTML` 注入的 `<script>` 默认不执行（CSP 策略）。

**解决**：用 DOMParser 解析 + 手动 `liveForm.submit()`（详见 §7.2）。

### 9.6 "TOML 解析错误: expected newline but got U+004D 'M'"

**原因**：TOML 不支持单位后缀，`10MB` 会报错。

**解决**：用字节数 `10485760`。

---

## 10. 沙箱 vs 生产切换

| 项 | 沙箱 | 生产 |
|---|---|---|
| APPID | `2021000123456789`（默认）| 真实 APPID |
| gateway-url | `https://openapi.alipaydev.com/gateway.do` | `https://openapi.alipay.com/gateway.do` |
| 签名类型 | RSA2 | RSA2 / SM2（需证书模式 + 申请） |
| 密钥 | 沙箱后台生成的 | 沙箱**不可用**，必须用生产密钥 |
| 签约 | 不需要 | 必须签约"电脑网站支付"或"手机网站支付" |
| 通知频率 | 测试触发 | 24h 内最多 4 次重试 |
| 回调地址 | 一个固定 | 最多 5 个（生产支持多） |

**部署生产只需**：

1. 换 5 个配置（APPID / 私钥 / 公钥 / gateway-url / 域名）
2. 跳过 frp（Nginx + 真证书）
3. 控制台后台改"授权回调地址"为生产 return-url

**代码零改动**。

---

## 11. 安全注意事项

| 项 | 注意 |
|---|---|
| 私钥 | 绝对不要进 git；走 Nacos 配置中心或环境变量 |
| 异步通知 | 验证 IP 来源（白名单 110.75.140.0/24, 140.205.94.0/24 等）|
| 金额校验 | 必须做，防伪造通知 |
| 幂等性 | 必须做，防重试导致状态错乱 |
| 日志 | 不要打印完整密钥 / 完整 form |
| HTTPS | 生产强制，沙箱可选但建议 |
| 白名单 | notify + return 必须加 WebMvcConfig 白名单 |

---

## 12. 相关文档

- [nacos-config-center.md](./nacos-config-center.md) — 沙箱密钥推荐存 Nacos 配置中心
- [test-login.md](./test-login.md) — 另一种"免登录体验"通道（适合只看不付钱的场景）

---

**变更记录**
- 2026-07-20: 实现支付宝沙箱支付端到端流程（提交 `61c2498`）
- 2026-07-21: 重写本设计文档（代码回退后，保留架构与踩坑总结供后续接入参考）