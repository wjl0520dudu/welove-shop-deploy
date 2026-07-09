# 基础设施速查表(backend/)

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
cd backend

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

Milvus 三兄弟(etcd/minio/milvus)用的是 bind mount 到 `backend/volumes/`,不是 named volume。

---

## 常见问题

**Q: RocketMQ 客户端在 IDEA 里连不上 broker?**
A: 检查 `backend/rocketmq/conf/broker.conf` 里 `brokerIP1`:
- Windows/Mac Docker Desktop → 保持 `host.docker.internal`
- Linux → 改成宿主机实际 IP(如 `192.168.1.100`)

**Q: Nacos 客户端连接报 "gRPC failed"?**
A: 确认 9848 端口(客户端 gRPC)开了。Nacos 2.x 起 gRPC 是主通道,不再走 8848。

**Q: 端口冲突?**
A: 上面表里所有端口都在同一个物理机的宿主机端口。冲突时改本 compose 文件的 `ports:` 左侧(宿主机端口),别改右侧(容器端口)。
