"""为多模态检索评测生成 mock 图文查询。

流程：
  1. 从 PG 随机抽 N 个 status=1 商品作为"金标"（source_product_id）
  2. 每个商品用 LLM 把 title + description 改写成一句自然语言查询
  3. 图片 URL 用商品主图
  4. 结果写到 tests/fixtures/mock_multimodal_queries.jsonl，供 eval 脚本读取

一次性调用 LLM，结果落盘，后续评测不再消耗 token。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select                             # noqa: E402

from app.infrastructure.persistence.database import get_session_factory             # noqa: E402
from app.infrastructure.llm.llm import get_llm                              # noqa: E402
from app.infrastructure.persistence.orm_models import CategoryORM, ProductORM   # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gen_mock_queries")

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mock_multimodal_queries.jsonl"


REWRITE_PROMPT = """你在为电商检索评测生成 mock 查询。

## 输入商品信息
- 标题：{title}
- 品牌：{brand}
- 品类：{category} / {sub_category}
- 标签：{tags}
- 描述：{description}

## 任务
把商品改写成一句用户可能会说的自然语言查询（模拟真实用户找商品的说法）。

## 规则
1. **不要出现完整的商品名**，模拟用户还不知道具体商品时的搜索语气
2. **可以说品类、卖点、使用场景、肤质/人群、价格区间**，让查询有辨识度
3. **一句话，20-40 字**
4. **口语化**，不要像广告词

## 示例
- 商品是"雅诗兰黛特润修护肌活精华露" → "推荐一款熬夜修护的抗初老精华，25+适合用的"
- 商品是"Nike Air Max 跑鞋" → "找一双缓震好的跑鞋，日常通勤和跑步都能穿"
- 商品是"云鲸扫拖一体机器人" → "有没有省事的扫地机器人，最好能自动拖地"

## 输出
只输出改写后的查询语句，不要解释、不要引号、不要多余符号。
"""


async def _fetch_random_products(n: int, seed: Optional[int]) -> List[Dict[str, Any]]:
    """从 PG 随机抽 n 个 status=1 且 image_url 非空的商品。"""
    sf = get_session_factory()
    async with sf() as s:
        stmt = (
            select(ProductORM, CategoryORM.name.label("category_name"))
            .outerjoin(CategoryORM, ProductORM.category_id == CategoryORM.id)
            .where(ProductORM.status == 1)
            .where(ProductORM.image_url.isnot(None))
            .where(ProductORM.image_url != "")
        )
        rows = (await s.execute(stmt)).all()

    products = []
    for p, cat_name in rows:
        products.append({
            "product_id": int(p.id),
            "title": p.title or "",
            "brand": p.brand or "",
            "category": cat_name or "",
            "sub_category": p.sub_category or "",
            "tags": p.tags or "",
            "description": (p.description or "")[:400],  # 太长的截断
            "image_url": p.image_url or "",
            "base_price": float(p.base_price) if p.base_price is not None else 0.0,
        })

    if seed is not None:
        random.seed(seed)
    random.shuffle(products)
    return products[:n]


async def _rewrite_to_query(llm, product: Dict[str, Any]) -> str:
    """用 LLM 把商品改写成用户查询。失败返回品类+品牌兜底。"""
    prompt = REWRITE_PROMPT.format(
        title=product["title"],
        brand=product["brand"] or "无",
        category=product["category"] or "无",
        sub_category=product["sub_category"] or "无",
        tags=product["tags"] or "无",
        description=product["description"] or "无",
    )
    try:
        resp = await llm.ainvoke(prompt)
        text = str(resp.content or "").strip()
        # 剥掉引号和多余标点
        text = text.strip('"').strip("'").strip("“").strip("”").strip("。")
        if 5 <= len(text) <= 100:
            return text
        logger.warning("改写结果长度异常 (%d 字符)，退回兜底：%r", len(text), text)
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM 改写失败，退回兜底：%s", e)

    # 兜底：品类 + 关键词
    parts = [product["sub_category"] or product["category"]]
    if product["brand"]:
        parts.append(product["brand"])
    return "推荐一款" + "".join(parts)


async def main_async(args) -> int:
    llm = get_llm()
    if llm is None:
        logger.error("LLM 未配置（缺 LLM_API_KEY），无法生成 mock 查询")
        return 2

    logger.info("从 PG 抽取 %d 个商品...", args.count)
    products = await _fetch_random_products(args.count, seed=args.seed)
    if len(products) < args.count:
        logger.warning("PG 里可用商品仅 %d 条（要求 %d）", len(products), args.count)
    if not products:
        logger.error("没抽到任何商品，退出")
        return 3

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("开始 LLM 改写 %d 条查询 → %s", len(products), out_path)
    queries = []
    for i, product in enumerate(products, start=1):
        query_text = await _rewrite_to_query(llm, product)
        record = {
            "query_id": f"q_{product['product_id']:06d}",
            "query_text": query_text,
            "query_image_url": product["image_url"],
            "source_product_id": product["product_id"],
            "source_title": product["title"],
            "source_category": product["category"],
            "source_sub_category": product["sub_category"],
            "source_base_price": product["base_price"],
        }
        queries.append(record)
        logger.info("[%d/%d] source_pid=%d → %r",
                    i, len(products), product["product_id"], query_text)

    with out_path.open("w", encoding="utf-8") as f:
        for q in queries:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    logger.info("完成：写入 %d 条 mock 查询到 %s", len(queries), out_path)
    return 0


def main():
    parser = argparse.ArgumentParser(description="生成多模态检索评测用 mock 查询")
    parser.add_argument("--count", type=int, default=20, help="生成多少条查询（默认 20）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认 42，可复现）")
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT),
                        help=f"输出 JSONL 路径（默认 {DEFAULT_OUT}）")
    args = parser.parse_args()

    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
