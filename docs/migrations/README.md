# docs/migrations — 数据库结构快照

> **用途**：开发期参考,不要当成生产迁移脚本跑。

---

## ⚠️ 重要警告

**这些文件包含 `DROP TABLE IF EXISTS` / `DROP SEQUENCE IF EXISTS` 语句。直接执行会清空现有数据！**

它们是 **Navicat Premium 导出的 PostgreSQL 完整结构快照**(2026-07-21),用于:

- ✅ 了解每个 schema 完整结构
- ✅ 新人入门数据库拓扑
- ✅ 对照 Flyway 迁移脚本看最终态
- ❌ **不能**作为初始化脚本(`psql -f 00x_*.sql`)
- ❌ **不能**作为 CI/CD 部署脚本

---

## 文件清单

| 文件 | 行数 | schema | 对应 Flyway |
|---|---|---|---|
| [001_user_svc.sql](./001_user_svc.sql) | 279 | user_svc | V1__init_user_svc.sql + V2__add_test_login_fields.sql |
| [002_admin_svc.sql](./002_admin_svc.sql) | 98 | admin_svc | V1 迁移(无版本号文件名) |
| [003_chat_svc.sql](./003_chat_svc.sql) | 549 | chat_svc | V1__init_chat_svc.sql + V2/V3/V4 |
| [004_product_svc.sql](./004_product_svc.sql) | 486 | product_svc | V1__init_product_svc.sql + V2__seed_products.sql |
| [005_trade_svc.sql](./005_trade_svc.sql) | 238 | trade_svc | V1__init_trade_svc.sql (V2 支付字段见内) |

---

## 与 Flyway 的关系

每个微服务自带 Flyway 迁移脚本:

```
services/user-service/src/main/resources/db/migration/V1__init_user_svc.sql
services/user-service/src/main/resources/db/migration/V2__add_test_login_fields.sql
services/admin-bff/src/main/resources/db/migration/...
services/chat-service/src/main/resources/db/migration/V1__init_chat_svc.sql
...
```

**Flyway 才是生产部署用的脚本**(自动执行,可重放,带版本号校验)。

**本目录的 dump 文件** 只是把最终态"拍个照",方便:

- 对照 Flyway 是否漏了字段
- 看现有索引 / 注释
- 反推某些注释里没写的设计意图

---

## 关键差异:本目录 vs Flyway

| 维度 | Flyway 脚本 | 本目录 dump |
|---|---|---|
| 用途 | 生产部署 | 开发期参考 |
| 语句 | `CREATE TABLE IF NOT EXISTS` 增量 | `DROP IF EXISTS` + `CREATE` 全量 |
| 数据 | 只动结构,不丢数据 | 会清掉所有现有数据 |
| 幂等 | 通过 Flyway 版本号保证 | 通过 `IF EXISTS` 保证 |
| 触发 | 服务启动时自动 | 手动 psql 执行 |

---

## 如果你想"完整重建数据库"

**不要用本目录的文件**。正确做法:

```bash
# 1. 删除整个数据库
dropdb -U postgres welove_shop_search

# 2. 重建空数据库
createdb -U postgres welove_shop_search

# 3. 启动任意微服务,Flyway 会自动建好所有表
cd services/user-service && mvn spring-boot:run
cd services/chat-service && mvn spring-boot:run
cd services/product-service && mvn spring-boot:run
cd services/trade-service && mvn spring-boot:run
cd admin-bff && mvn spring-boot:run
```

Flyway 会按 `V1 → V2 → V3 → V4` 顺序执行所有迁移,无需手动干预。

---

## 更新时机

当你做了下面任一改动时,**重新导出 dump 替换本目录文件**:

- 改了任何 `V*.sql` 迁移脚本(新增 / 修改字段)
- 手动给某个表加了索引 / 注释
- 给某个表加了新约束

操作:Navicat Premium → 选 schema → 右键 → 转储 SQL 文件 → 仅结构 → 替换 `00X_xxx.sql`。