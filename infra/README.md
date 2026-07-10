# 基础设施速查表(infra/)

本目录存放**本地开发用的中间件 docker-compose**。生产部署另有方案,不在本文档范围。

---

## 一图看清端口分配

| 组件 | 容器名 | 宿主机端口 | 用途 |
|-----|-------|----------|------|
| **MySQL 8.0** | welove-shop-mysql | 3306 | 单体历史数据/`welove_shop_db` |
| **Redis 7** | welove-shop-redis | 6379 | 缓存/会话/限流 |
| **PostgreSQL 16 + pgvector** | welove-shop-postgres | 5432 | 微服务主库 `welove_shop_search` |
| **Milvus 2.6.8** | milvus-standalone | 19530, 9091 | 向量库 |
| ├─ etcd | milvus-etcd | (内部) | Milvus 元数据 |
| ├─ MinIO | milvus-minio | 9000, 9001 | Milvus 对象存储 |
| └─ Attu | milvus-attu | 8091 | Milvus 可视化 |
| **Nacos 2.3.2** | welove-shop-nacos | 8848, 9848, 9849 | 注册中心 + 配置中心 |
| **RocketMQ 5.3.1 NameServer** | welove-shop-rmqnamesrv | 9876 | MQ 名称服务 |
| **RocketMQ 5.3.1 Broker** | welove-shop-rmqbroker | 10909, 10911, 10912 | MQ Broker |
| **RocketMQ Dashboard** | welove-shop-rmqdashboard | 8181 | MQ 可视化 |

**微服务预留端口(不与中间件冲突):**

| 服务 | 端口 |
|-----|------|
| gateway | 8080 |
| user-service | 8081 |
| product-service | 8082 |
| trade-service | 8083 |
| chat-service | 8084 |
| admin-bff | 8090 |

---

## 全部起来(按依赖顺序)

```bash
cd infra

# 1. 数据层(MySQL + Redis + PG)
docker compose -f docker-compose.yml up -d

# 2. 向量库(Milvus 单机)
docker compose -f milvus-standalone-docker-compose.yml up -d

# 3. 注册配置中心(Nacos)
docker compose -f nacos-standalone-docker-compose.yml up -d

# 4. 消息队列(RocketMQ)
docker compose -f rocketmq-docker-compose.yml up -d
```

**检查全部健康:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

---

## 关键访问信息

### Nacos 控制台
- URL: http://localhost:8848/nacos
- 账号: `nacos` / `nacos`
- 命名空间约定:
  - `public` — 默认(骨架阶段用)
  - `dev` / `test` / `prod` — 后续按环境隔离

### Milvus Attu
- URL: http://localhost:8091
- Milvus 地址: `standalone:19530`(容器网络内)

### RocketMQ Dashboard
- URL: http://localhost:8181
- NameServer: `namesrv:9876`(容器网络内)

### MinIO Console(Milvus 用)
- URL: http://localhost:9001
- 账号: `minioadmin` / `minioadmin`

### PostgreSQL
- 主机: `localhost:5432`
- 用户: `root` / `12345678`
- 主库: `welove_shop_search`(微服务将在此库内按 schema 隔离:user_svc / product_svc / trade_svc / chat_svc)

### MySQL
- 主机: `localhost:3306`
- 用户: `root` / `12345678`
- 主库: `welove_shop_db`(单体历史数据,微服务不再新写入)

### Redis
- 主机: `localhost:6379`
- 无密码(骨架阶段)

---

## 独立停止/重启单个组件

```bash
# 举例:只重启 Nacos
docker compose -f nacos-standalone-docker-compose.yml restart

# 只停 RocketMQ
docker compose -f rocketmq-docker-compose.yml down

# 完全清空 Nacos(慎用,删数据卷)
docker compose -f nacos-standalone-docker-compose.yml down -v
```

---

## 数据卷(named volume)清单

| 卷名 | 归属 | 说明 |
|-----|------|------|
| `backend_mysql_data` | MySQL | 表数据 |
| `backend_redis_data` | Redis | 快照 |
| `backend_pgdata` | PostgreSQL | 表数据 |
| `backend_nacos_data` | Nacos | derby 数据+配置 |
| `backend_nacos_logs` | Nacos | 日志 |
| `backend_rmq_namesrv_logs` | RocketMQ NS | 日志 |
| `backend_rmq_broker_logs` | RocketMQ Broker | 日志 |
| `backend_rmq_broker_store` | RocketMQ Broker | 消息存储 |

Milvus 三兄弟(etcd/minio/milvus)用的是 bind mount 到 `infra/volumes/`,不是 named volume。

---

## 常见问题

**Q: RocketMQ 客户端在 IDEA 里连不上 broker?**
A: 检查 `infra/rocketmq/conf/broker.conf` 里 `brokerIP1`:
- Windows/Mac Docker Desktop → 保持 `host.docker.internal`
- Linux → 改成宿主机实际 IP(如 `192.168.1.100`)

**Q: Nacos 客户端连接报 "gRPC failed"?**
A: 确认 9848 端口(客户端 gRPC)开了。Nacos 2.x 起 gRPC 是主通道,不再走 8848。

**Q: 端口冲突?**
A: 上面表里所有端口都在同一个物理机的宿主机端口。冲突时改本 compose 文件的 `ports:` 左侧(宿主机端口),别改右侧(容器端口)。

---

## Ph3 服务接入 Nacos 后的启动验证

**前置条件:** 已按上面顺序起好中间件,尤其 Nacos 容器健康。

### 1. IDEA 里逐个启动 6 个服务

在 IDEA 里配置 6 个 Spring Boot 启动项(建议放到一个 Compound 里一键起),对应主类:

| 服务 | 主类 | 端口 |
|-----|-----|------|
| gateway | `com.welove.shop.gateway.GatewayApplication` | 8080 |
| user-service | `com.welove.shop.user.UserServiceApplication` | 8081 |
| product-service | `com.welove.shop.product.ProductServiceApplication` | 8082 |
| trade-service | `com.welove.shop.trade.TradeServiceApplication` | 8083 |
| chat-service | `com.welove.shop.chat.ChatServiceApplication` | 8084 |
| admin-bff | `com.welove.shop.admin.AdminBffApplication` | 8090 |

或者用命令行(需要先 `mvn install`):

```bash
# 每个服务一个终端
java -jar gateway/target/gateway.jar
java -jar services/user-service/target/user-service.jar
java -jar services/product-service/target/product-service.jar
java -jar services/trade-service/target/trade-service.jar
java -jar services/chat-service/target/chat-service.jar
java -jar admin-bff/target/admin-bff.jar
```

### 2. 打开 Nacos 控制台验证

访问 http://localhost:8848/nacos(账号 `nacos` / 密码 `nacos`)

进入 **服务管理 → 服务列表**,应能看到 6 个实例:

| 服务名 | 实例数 | 健康 |
|-------|-------|-----|
| gateway | 1 | true |
| user-service | 1 | true |
| product-service | 1 | true |
| trade-service | 1 | true |
| chat-service | 1 | true |
| admin-bff | 1 | true |

### 3. 通过网关自动路由验证

网关配置了 `discovery.locator.enabled: true`,可用 `/{service-name}/**` 直接透传:

```bash
# 通过网关访问 user-service 的健康端点
curl http://localhost:8080/user-service/actuator/health

# 直连 user-service 本机端点对比
curl http://localhost:8081/actuator/health

# 二者返回都应是 {"status":"UP",...}
```

### 4. 各服务独立健康检查

```bash
curl http://localhost:8080/actuator/health   # gateway
curl http://localhost:8081/actuator/health   # user
curl http://localhost:8082/actuator/health   # product
curl http://localhost:8083/actuator/health   # trade
curl http://localhost:8084/actuator/health   # chat
curl http://localhost:8090/actuator/health   # admin-bff
```

### 常见问题(Ph3)

**Q: 服务启动报 "Client not connected, current status:STARTING"**
A: Nacos 客户端 gRPC 端口(9848)没通。检查 `docker ps` 里 nacos 容器 9848 端口映射,或 Nacos 容器没起完就启服务了。等 Nacos 健康(60s+)再起服务。

**Q: 服务日志有 "user not found!" / "unknown user"**
A: 服务的 `application.yml` 里 `username/password` 与 Nacos 不一致。骨架期我们用默认 `nacos/nacos`,如果改过 Nacos 密码,同步改所有服务配置。

**Q: 网关的 /{service-name}/** 转发 404?**
A: 检查 gateway 的 `spring.cloud.gateway.discovery.locator.lower-case-service-id: true`,注意用户 URL 里 service-name 要用**小写**(如 `/user-service/...` 而不是 `/USER-SERVICE/...`)。

---

## user-service 全链路验证(feat/ms-user)

**前置条件:**
1. Docker 中间件已启动:PostgreSQL(5432) + Redis(6379) + Nacos(8848)
2. Nacos 控制台可登录 http://localhost:8848/nacos(nacos/nacos)

### 启动 user-service

VSCode Spring Boot Dashboard 里点 `user-service` 的 ▶️,或命令行:

```bash
mvn -pl services/user-service spring-boot:run
```

**首次启动会:**
- Flyway 自动创建 `user_svc` schema
- 执行 `V1__init_user_svc.sql` 创建 users / address / user_browse_history / user_favorite 四张表
- 注册到 Nacos(可在控制台 `服务管理 → 服务列表` 看到 user-service)

### curl 全链路验证

**步骤 1:发送短信验证码**(骨架期 mock,验证码打印在 user-service 控制台)

```bash
curl -s -X POST "http://localhost:8081/api/auth/sendCode?phone=13800138000"
# 期望: {"code":0,"message":"success","data":"验证码已发送"}
```

**在 user-service 控制台查看 `[SMS-MOCK] 已发送验证码到 13800138000: 123456` 的日志,复制 6 位验证码。**

**步骤 2:登录**(用上一步的验证码;未注册手机号会自动建账号)

```bash
curl -s -X POST http://localhost:8081/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","code":"123456"}'
# 期望: {"code":0,"message":"success","data":{"user":{...},"token":"eyJhbG...","refreshToken":"eyJhbG...","tokenType":"Bearer"}}
```

**保存返回的 `token` 值到环境变量:**
```bash
export TOKEN='粘贴上面返回的 token'
```

**步骤 3:查自己资料**(需要 token,验证 JWT 拦截器)

```bash
curl -s http://localhost:8081/api/auth/profile -H "Authorization: Bearer $TOKEN"
# 期望: {"code":0,"message":"success","data":{"id":1,"username":"用户8000",...}}
```

**步骤 4:更新资料**

```bash
curl -s -X POST http://localhost:8081/api/auth/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"username":"张三","gender":1,"skinType":"油皮","preferenceTags":["补水","抗老"]}'
# 期望: 返回更新后的 User(preferenceTags 存为 JSONB)
```

**步骤 5:地址簿 CRUD**

```bash
# 添加地址
curl -s -X POST http://localhost:8081/api/address/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"receiverName":"张三","phone":"13800138000","province":"广东","city":"深圳","district":"南山","detail":"科兴路 1 号","isDefault":1}'

# 列表
curl -s http://localhost:8081/api/address/list -H "Authorization: Bearer $TOKEN"

# 设默认(将 id=1 设为默认)
curl -s -X PUT "http://localhost:8081/api/address/setDefault?id=1" -H "Authorization: Bearer $TOKEN"

# 删除
curl -s -X DELETE "http://localhost:8081/api/address/delete?id=1" -H "Authorization: Bearer $TOKEN"
```

**步骤 6:浏览历史**

```bash
# 上报一条(product-service 未落地,productId 用假数据)
curl -s -X POST http://localhost:8081/api/user/browse-history \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"productId":100,"source":"详情页","durationSec":30}'

# 列表(骨架期 productName/image/price 为空,后续 Feign 补齐)
curl -s http://localhost:8081/api/user/browse-history -H "Authorization: Bearer $TOKEN"

# 删除(替换 {historyId} 为实际 id)
curl -s -X DELETE http://localhost:8081/api/user/browse-history/1 -H "Authorization: Bearer $TOKEN"
```

**步骤 7:商品收藏**

```bash
# 添加(幂等)
curl -s -X POST http://localhost:8081/api/user/favorites/100 -H "Authorization: Bearer $TOKEN"

# 列表
curl -s http://localhost:8081/api/user/favorites -H "Authorization: Bearer $TOKEN"

# 取消
curl -s -X DELETE http://localhost:8081/api/user/favorites/100 -H "Authorization: Bearer $TOKEN"
```

**步骤 8:异常路径**

```bash
# 无 token 访问受保护接口 -> 期望 UNAUTHORIZED
curl -s http://localhost:8081/api/auth/profile
# 期望: {"code":10002,"message":"未登录或登录已过期","data":null}

# 手机号格式错 -> 期望 20001
curl -s -X POST "http://localhost:8081/api/auth/sendCode?phone=12345"
# 期望: {"code":20001,"message":"手机号格式错误","data":null}

# 验证码错误 -> 期望 20004
curl -s -X POST http://localhost:8081/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","code":"000000"}'
# 期望: {"code":20004,"message":"验证码错误","data":null}
```

### 直接从 PG 验数据

```bash
docker exec -it welove-shop-postgres psql -U root -d welove_shop_search \
  -c "SET search_path TO user_svc; SELECT id, username, phone, gender, skin_type, preference_tags FROM users;"
```

期望能看到刚才注册/更新的用户,`preference_tags` 显示为 JSON 数组。

---

## product-service 全链路验证(feat/ms-product)

**前置条件:**
1. Docker 中间件已启动:PostgreSQL(5432) + Redis(6379) + Nacos(8848)
2. Nacos 控制台可登录 http://localhost:8848/nacos(nacos/nacos)

### 启动 product-service

VSCode Spring Boot Dashboard 里点 `product-service` 的 ▶️,或命令行:

```bash
mvn -pl services/product-service spring-boot:run
```

**首次启动会:**
- Flyway V1 创建 `product_svc` schema + 7 张表
- Flyway V2 导入 100 商品 + 4 分类 + 585 SKU + 100 图片 + 439 FAQ + 453 评论
- 注册到 Nacos(可在控制台 `服务管理 → 服务列表` 看到 product-service)

### curl 全链路验证

**步骤 1:分类列表**(匿名访问)

```bash
curl -s http://localhost:8082/api/category/list
# 期望: 返回 4 个分类,美妆护肤/数码电子/服饰运动/食品生活
```

**步骤 2:商品列表分页**

```bash
# 全部商品第 1 页 20 条(默认按销量倒序)
curl -s "http://localhost:8082/api/product/list?page=1&size=20"

# 美妆护肤(categoryId=1),按价格升序
curl -s "http://localhost:8082/api/product/list?categoryId=1&page=1&size=10&sortBy=price&sortOrder=asc"

# 期望 records 里包含商品,total=100(全部)或 25(单分类)
```

**步骤 3:关键词搜索**

```bash
# 原词
curl -s "http://localhost:8082/api/product/search?keyword=雅诗兰黛&limit=5"

# 同义词扩展(护肤 -> 精华/面霜/乳液/爽肤水/面膜/眼霜)
curl -s "http://localhost:8082/api/product/search?keyword=护肤&limit=5"

# 期望返回多个匹配商品
```

**步骤 4:热门商品**(第一次调用会击穿到 DB,后续 60s 内走 Redis 缓存)

```bash
curl -s "http://localhost:8082/api/product/hot?limit=5"

# 看 Redis 缓存是否命中
docker exec welove-shop-redis redis-cli KEYS 'product:*'
# 期望看到 product:hot:5
```

**步骤 5:商品详情(聚合)**

```bash
curl -s http://localhost:8082/api/product/1
# 期望: data 包含 product/skus(3 条)/images/faqs/reviews(前 10)

# 再次调用 —— Redis 命中,速度更快
curl -s http://localhost:8082/api/product/1

# Redis 里能看到 product:detail:1
docker exec welove-shop-redis redis-cli KEYS 'product:detail:*'
```

**步骤 6:商品资源分开查**

```bash
curl -s http://localhost:8082/api/product/1/skus
curl -s http://localhost:8082/api/product/1/images
curl -s http://localhost:8082/api/product/1/faqs
```

**步骤 7:提交评价(需登录 token)**

先从 user-service 拿一个 token(参考上面 user-service 验证步骤 1-2)。

```bash
export TOKEN='<user-service 拿到的 token>'
curl -s -X POST http://localhost:8082/api/product/1/reviews \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"nickname":"tester","rating":5,"content":"very good","isAnonymous":0}'
# 期望 code=0,返回带 id 的评价
```

**步骤 8:异常路径**

```bash
# 无 token 提交评价 -> 401 (UNAUTHORIZED)
curl -s -X POST http://localhost:8082/api/product/1/reviews \
  -H "Content-Type: application/json" \
  -d '{"nickname":"anon","rating":5,"content":"test"}'
# 期望 code=10002

# 商品不存在
curl -s http://localhost:8082/api/product/999999
# 期望 code=30001, message=商品不存在

# rating 超范围
curl -s -X POST http://localhost:8082/api/product/1/reviews \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"rating":10,"content":"test"}'
# 期望 code=30101, message=评分必须在 1-5 之间
```

### 直接从 PG 验数据

```bash
docker exec welove-shop-postgres psql -U root -d welove_shop_search -c "
SET search_path TO product_svc;
SELECT 'category' AS tbl, COUNT(*) FROM category
UNION ALL SELECT 'product',       COUNT(*) FROM product
UNION ALL SELECT 'product_sku',   COUNT(*) FROM product_sku
UNION ALL SELECT 'product_image', COUNT(*) FROM product_image
UNION ALL SELECT 'product_faq',   COUNT(*) FROM product_faq
UNION ALL SELECT 'product_review', COUNT(*) FROM product_review;
"
```

期望:category 4 / product 100 / product_sku 585 / product_image 100 / product_faq 439 / product_review 453。

### 直接看 Redis 缓存

```bash
# 所有 product 缓存 key
docker exec welove-shop-redis redis-cli KEYS 'product:*'

# 看某 key TTL 剩余秒数
docker exec welove-shop-redis redis-cli TTL 'product:detail:1'

# 手动清空(排查用)
docker exec welove-shop-redis redis-cli --scan --pattern 'product:*' | \
  xargs -I{} docker exec welove-shop-redis redis-cli DEL {}
```

---

## Gateway 显式路由 + 分层鉴权(feat/ms-gateway)

**前置:** Nacos + PG + Redis 三个中间件在跑,6 个微服务全部启动(gateway + user + product + trade + chat + admin-bff)。

### 路由前缀映射表

Gateway 使用显式路由 + `StripPrefix=1`,把外部路径的第一段(服务名)剥掉后转发到对应服务:

| Gateway 入口 | 转发目标 |
|-------------|---------|
| `POST /user/api/auth/login` | `user-service :8081` `/api/auth/login` |
| `GET  /user/api/auth/profile` | `user-service :8081` `/api/auth/profile` |
| `GET  /product/api/product/list` | `product-service :8082` `/api/product/list` |
| `GET  /product/api/category/list` | `product-service :8082` `/api/category/list` |
| `POST /trade/api/order/create` | `trade-service :8083` `/api/order/create` |
| `GET  /chat/api/chat/conversations` | `chat-service :8084` `/api/chat/conversations` |
| `POST /admin/api/admin/login` | `admin-bff :8090` `/api/admin/login` |
| `GET  /admin/api/admin/dashboard/stats` | `admin-bff :8090` `/api/admin/dashboard/stats` |

### 分层鉴权设计

**架构:** Gateway 主鉴权 + 下游 JwtInterceptor 兜底 = 双重保险,零信任。

1. Gateway `JwtAuthGlobalFilter`(order=-100)校验 JWT 签名+过期
2. 白名单(`gateway-auth.whitelist`)命中直接放行
3. 校验通过后塞 request header 透传下游:
   - `X-User-Id` = claims.subject
   - `X-Username` = claims.username
   - `X-Role` = claims.role
4. 下游服务的 `JwtInterceptor` 仍从 `Authorization` 解析(骨架期不改),网关塞头为未来分层做准备

### 5 步 curl 验证

**步骤 1:未登录访问受保护接口 → 401**

```bash
curl -s http://localhost:8080/user/api/auth/profile
# 期望: {"code":10002,"message":"缺少 Authorization Bearer token",...}
```

**步骤 2:通过 gateway 登录拿 token**

```bash
# 发验证码(user-service 控制台会打印)
curl -s -X POST "http://localhost:8080/user/api/auth/sendCode?phone=13800138000"

# 从 Redis 拿验证码
CODE=$(docker exec welove-shop-redis redis-cli GET "sms:code:13800138000")

# 登录
LOGIN=$(curl -s -X POST http://localhost:8080/user/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"phone\":\"13800138000\",\"code\":\"$CODE\"}")
TOKEN=$(echo "$LOGIN" | grep -oE '"token":"[^"]+"' | head -1 | sed 's/"token":"//' | sed 's/"$//')
```

**步骤 3:带 token 访问受保护接口 → 200**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/user/api/auth/profile
# 期望: {"code":0,"message":"success","data":{...}}
```

**步骤 4:商品接口白名单免鉴权**

```bash
curl -s "http://localhost:8080/product/api/product/list?page=1&size=3"
# 期望: 直接返回 3 个商品,不用 token
```

**步骤 5:Admin 登录 + Dashboard(role=ADMIN 双重校验)**

```bash
# Admin 登录(gateway 白名单)
ADMIN_LOGIN=$(curl -s -X POST http://localhost:8080/admin/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')
ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | grep -oE '"accessToken":"[^"]+"' | head -1 | \
  sed 's/"accessToken":"//' | sed 's/"$//')

# Dashboard(gateway JWT 校验通过,admin-bff 内部 AdminInterceptor 二次校验 role=ADMIN)
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8080/admin/api/admin/dashboard/stats
# 期望: {"code":0,"data":{"userCount":..,"productCount":100,"orderCount":..,"conversationCount":..,"todayRevenue":..}}

# 拿普通用户 token 访问 admin(应被 admin-bff 内部拦下)
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/admin/api/admin/dashboard/stats
# 期望: {"code":60003,"message":"非管理员 token",...}
```

### 常见问题

**Q: 访问 /user/api/xxx 返回 503?**
A: user-service 未起或未注册到 Nacos。`docker ps` 看 Nacos,浏览器打开 `http://localhost:8848/nacos` 检查服务列表。gateway 全局错误处理器会把 `NotFoundException` 转成 503+"下游服务不可用"。

**Q: 明明有 token 但 401?**
A:
1. Header 格式:`Authorization: Bearer <token>`(注意 `Bearer ` 后有空格)
2. token 过期(默认 1 小时)
3. 各服务 `jwt.secret` 是否一致(骨架期都用父 POM 默认值)

**Q: 前端 CORS 报错?**
A: Gateway 已配全局 CORS(`allowedOriginPatterns=*` + `allowCredentials=true`)。检查请求 origin,浏览器 Network 面板看响应是否带 `Access-Control-Allow-Origin`。

**Q: 想看 gateway 加载了哪些路由?**
A: `curl http://localhost:8080/actuator/gateway/routes` 列出所有路由规则。
