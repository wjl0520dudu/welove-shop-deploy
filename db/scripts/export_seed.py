"""
从 monolith MySQL 导出 product 相关 6 张表数据,生成 PG 兼容 SQL 到 Flyway V2 迁移文件。

- 连 MySQL(容器 welove-shop-mysql 端口 3306,root/12345678,库 welove_shop_db)
- 6 张表:category / product / product_sku / product_image / product_faq / product_review
- 表名前缀 product_svc. 用于 schema-based 微服务隔离
- JSON 字段(product_sku.properties)直接以 JSON 字符串写入,PG JSONB 自动解析
- id 列显式插入,尾部用 setval 把 IDENTITY 序列推到 max(id)+1 避免后续冲突

用法:python export_seed.py <output.sql>
"""
import json
import pymysql
import sys

TABLES = [
    # (mysql_table, pg_table_full_name, [列名列表], {json_cols})
    ("category",
     "product_svc.category",
     ["id", "name", "description", "icon_url", "sort_order", "is_active", "create_time"],
     set()),
    ("product",
     "product_svc.product",
     ["id", "product_code", "category_id", "title", "brand", "sub_category", "base_price",
      "image_url", "description", "tags", "rating", "review_count", "sales_count",
      "status", "embedding_status", "create_time", "update_time"],
     set()),
    ("product_sku",
     "product_svc.product_sku",
     ["id", "product_id", "sku_code", "properties", "price", "stock", "is_default", "create_time"],
     {"properties"}),
    ("product_image",
     "product_svc.product_image",
     ["id", "product_id", "image_url", "image_type", "sort_order", "create_time"],
     set()),
    ("product_faq",
     "product_svc.product_faq",
     ["id", "product_id", "question", "answer", "sort_order", "create_time"],
     set()),
    ("product_review",
     "product_svc.product_review",
     ["id", "product_id", "user_id", "nickname", "rating", "content", "is_anonymous", "create_time"],
     set()),
]


def pg_literal(value, is_json=False):
    """把 Python 值转成 PG SQL 字面量。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"        # 我们的 schema 里布尔用 SMALLINT
    if isinstance(value, (int, float)):
        return str(value)
    if is_json:
        # pymysql 返回的 JSON 已经是 dict/list,序列化后再包 quote
        if isinstance(value, (dict, list)):
            s = json.dumps(value, ensure_ascii=False)
        else:
            # 字符串形式的 JSON,直接用
            s = str(value)
        return "'" + s.replace("'", "''") + "'::jsonb"
    # 字符串 / 日期时间(datetime 用 str 就好)
    s = str(value)
    return "'" + s.replace("'", "''") + "'"


def main():
    if len(sys.argv) < 2:
        print("usage: python export_seed.py <output.sql>", file=sys.stderr)
        sys.exit(1)
    output_path = sys.argv[1]

    conn = pymysql.connect(
        host="127.0.0.1", port=3306,
        user="root", password="12345678",
        database="welove_shop_db",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        # 用二进制模式写,newline="\n" 保证 Unix 换行,不加 BOM
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            def w(line=""):
                f.write(line + "\n")

            w("-- =====================================================================")
            w("-- Flyway V2:product-service seed 数据(从 monolith MySQL 导出)")
            w("-- 6 张表:category / product / product_sku / product_image / product_faq / product_review")
            w("-- 生成时通过 pymysql 直连 MySQL 8.0,保留 JSON 字段结构")
            w("-- =====================================================================")
            w()
            w("SET search_path TO product_svc;")
            w()

            with conn.cursor() as cur:
                for mysql_tbl, pg_tbl, cols, json_cols in TABLES:
                    col_list = ", ".join(cols)
                    cur.execute(f"SELECT {col_list} FROM {mysql_tbl} ORDER BY id")
                    rows = cur.fetchall()
                    if not rows:
                        w(f"-- {pg_tbl}: 0 rows,skip")
                        w()
                        continue

                    w(f"-- ---------- {pg_tbl} ({len(rows)} rows) ----------")
                    w(f"INSERT INTO {pg_tbl} ({col_list}) OVERRIDING SYSTEM VALUE VALUES")
                    lines = []
                    for row in rows:
                        vals = [pg_literal(row[c], is_json=(c in json_cols)) for c in cols]
                        lines.append("(" + ", ".join(vals) + ")")
                    w(",\n".join(lines) + ";")

                    max_id = max(int(r["id"]) for r in rows)
                    w(f"SELECT setval(pg_get_serial_sequence('{pg_tbl}', 'id'), {max_id});")
                    w()

            w("-- V2 completed.")

        print(f"[OK] wrote {output_path}", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
