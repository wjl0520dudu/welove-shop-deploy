# db/scripts

微服务阶段一次性的数据迁移辅助脚本。

## export_seed.py

**用途:** 从 monolith MySQL 导出 product 相关 6 张表数据,生成 PG 兼容的 Flyway V2 迁移 SQL。

**前置:** MySQL 容器 `welove-shop-mysql` 已启动,内含单体 `welove_shop_db` 库的完整种子数据。

**运行:**

```bash
python db/scripts/export_seed.py <output.sql>
```

例如生成到 product-service 的 Flyway 目录:

```bash
python db/scripts/export_seed.py \
  services/product-service/src/main/resources/db/migration/V2__seed_products.sql
```

**导出的内容:**
- category (4 rows)
- product (100 rows)
- product_sku (~585 rows)
- product_image (~100 rows)
- product_faq (~439 rows)
- product_review (~453 rows)

**注意事项:**
- 需要 `pymysql`。Windows 用 `wlagt` conda 环境自带。
- JSONB 字段(product_sku.properties)自动序列化为合法 JSON。
- id 显式插入用 `OVERRIDING SYSTEM VALUE`,末尾用 `setval` 推 IDENTITY 序列到 max+1。
- 输出 UTF-8 无 BOM,Unix 换行。

**什么时候会重新跑?**
一般不会。V2 已入 Flyway 迁移历史,新库建表 + 灌数据一次到位。只有当 monolith 数据源刷新、需要用最新数据重新生成 V2 时才跑。
