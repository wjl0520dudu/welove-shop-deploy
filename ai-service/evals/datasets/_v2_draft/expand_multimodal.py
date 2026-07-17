"""扩 multimodal case 8 → 20，同时把 image_url 替换为 Unsplash 免费图（避免与训练集污染）。

Unsplash 图直接用官方 CDN 直链（可 hotlink），无需你上传：
- 每张图选择"用户视角实拍/生活场景"，非商品官方图
- 覆盖 4 大品类 + 5 类问法（找同款/找相似/图+知识/图+偏好/纯图/多约束/对抗）
"""
import json
from pathlib import Path

DATASET = Path("evals/datasets/agent_golden_cases.jsonl")

# ═══════════════════════════════════════════════════════════════════
# 20 条 multimodal case 的完整定义（覆盖 img-001 ~ img-020）
# 每条 image_url 都是 Unsplash 免费商用直链，非商品官方图
# ═══════════════════════════════════════════════════════════════════
UNSPLASH_BASE = "https://images.unsplash.com"

MULTIMODAL_CASES = [
    # ── 原 8 条：替换成 Unsplash 图 ────────────────────
    {
        "id": "img-001", "scenario": "multimodal_shopping", "tags": ["image", "food", "find_similar"],
        "input": "找和图片中同类的方便面",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1552611052-33e04de081de?w=800"},  # instant noodle bowl
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["方便食品"],
            "retrieval_grades": {"86": 2, "87": 2, "95": 2, "96": 2},
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-002", "scenario": "multimodal_shopping", "tags": ["image", "sport", "find_similar"],
        "input": "按图找类似的跑鞋",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1542291026-7eec264c27ff?w=800"},  # red Nike running shoes
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["跑步鞋"],
            "retrieval_grades": {"57": 2, "58": 2, "59": 2, "60": 1},
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-003", "scenario": "multimodal_shopping", "tags": ["image", "beauty", "image_plus_knowledge"],
        "input": "图片里这款防晒适合油皮吗，找几款同类",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1556228720-195a672e8a03?w=800"},  # sunscreen bottle
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["防晒"],
            "retrieval_grades": {"10": 2, "23": 2, "6": 1},
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-004", "scenario": "multimodal_shopping", "tags": ["image", "digital", "find_similar"],
        "input": "找和这张图类似的真无线耳机",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1590658268037-6bf12165a8df?w=800"},  # wireless earbuds
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["真无线耳机"],
            "retrieval_grades": {"32": 2, "43": 2},
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-005", "scenario": "multimodal_shopping", "tags": ["image", "beauty", "image_plus_preference"],
        "input": "按图找同类面霜，优先清爽型",
        "request": {
            "image_url": f"{UNSPLASH_BASE}/photo-1611930022073-b7a4ba5fcccd?w=800",  # face cream jar
            "preference_tags": ["清爽"],
        },
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["面霜"],
            "retrieval_grades": {"12": 2, "7": 1, "8": 1},
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-006", "scenario": "multimodal_shopping", "tags": ["image", "image_only"],
        "input": "",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1585386959984-a4155224a1ad?w=800"},  # cosmetic product
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-007", "scenario": "multimodal_shopping", "tags": ["image", "clothes", "find_similar"],
        "input": "按图找同款男士 T 恤",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1521572163474-6864f9cf17ab?w=800"},  # men's white tshirt
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["短袖T恤"],
            "retrieval_grades": {"51": 2, "52": 2, "53": 2},
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-008", "scenario": "multimodal_shopping", "tags": ["image", "food", "image_plus_search"],
        "input": "图里这瓶饮料是什么，还有类似的推荐吗",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1622483767028-3f66f32aef97?w=800"},  # beverage bottle
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "max_latency_ms": 20000,
        },
    },
    # ── 12 条新增 ────────────────────
    # 同品类不同问法（4）
    {
        "id": "img-009", "scenario": "multimodal_shopping", "tags": ["image", "beauty", "image_plus_budget"],
        "input": "按图找同款防晒，300 元以内",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1526947425960-945c6e72858f?w=800"},  # sunscreen tube
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["防晒"],
            "retrieval_grades": {"6": 2, "10": 2, "23": 2},
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-010", "scenario": "multimodal_shopping", "tags": ["image", "sport", "image_plus_brand"],
        "input": "找图片里同类型 Nike 品牌的鞋",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1595950653106-6c9ebd614d3a?w=800"},  # sneakers
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "retrieval_grades": {"57": 2},  # 只有 Nike Pegasus 匹配品牌
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-011", "scenario": "multimodal_shopping", "tags": ["image", "digital", "image_plus_scenario"],
        "input": "图里这款平板电脑，学生学习用推荐一款",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1544244015-0df4b3ffc6b0?w=800"},  # tablet
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["平板电脑"],
            "retrieval_grades": {"50": 2, "44": 2, "36": 1},  # iPad Air 学习款
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-012", "scenario": "multimodal_shopping", "tags": ["image", "clothes", "image_plus_price_range"],
        "input": "找图里这种款式的男士休闲裤，200-500 元",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1584865288642-42078afe6942?w=800"},  # men casual pants
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "retrieval_grades": {"54": 2, "56": 2},  # adidas + Nike 运动长裤符合价格
            "max_latency_ms": 20000,
        },
    },
    # 跨品类推荐（2）
    {
        "id": "img-013", "scenario": "multimodal_shopping", "tags": ["image", "cross_category", "outfit"],
        "input": "给这双跑鞋搭配一款运动 T 恤",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1608231387042-66d1773070a5?w=800"},  # running shoes
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "retrieval_grades": {"70": 2, "71": 2, "53": 1},  # 速干 T 恤
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-014", "scenario": "multimodal_shopping", "tags": ["image", "cross_category", "gift"],
        "input": "想送这类护肤品当礼物，能推荐配套的礼盒吗",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1570194065650-d99fb4bedf0a?w=800"},  # skincare set
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "max_latency_ms": 20000,
        },
    },
    # 复杂图 + 多约束（3）
    {
        "id": "img-015", "scenario": "multimodal_shopping", "tags": ["image", "beauty", "multi_constraint"],
        "input": "图里这款精华，敏感肌可用的，预算 500 以下",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1631730359585-38a4935cbec4?w=800"},  # serum bottle
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["精华"],
            "retrieval_grades": {"5": 2, "9": 2, "18": 2},  # 科颜氏/珀莱雅/The Ordinary
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-016", "scenario": "multimodal_shopping", "tags": ["image", "sport", "multi_constraint"],
        "input": "图里这类型的鞋，男士 39 码，1000 以内",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1600185365483-26d7a4cc7519?w=800"},  # basketball shoes
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True, "product_categories": ["篮球鞋"],
            "retrieval_grades": {"62": 2},  # 安踏 KT9 ¥999 符合
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-017", "scenario": "multimodal_shopping", "tags": ["image", "food", "multi_constraint"],
        "input": "图里这种健康饮料，0 糖 0 脂的",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1622483767028-3f66f32aef97?w=800"},  # sparkling water
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "retrieval_grades": {"79": 2, "99": 2, "90": 1},  # 元气森林 + 可口可乐零度
            "max_latency_ms": 20000,
        },
    },
    # 对抗/边界（3）
    {
        "id": "img-018", "scenario": "multimodal_shopping", "tags": ["image", "adversarial", "unrelated"],
        "input": "找这个的同款",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1533738363-b7f9aef128ce?w=800"},  # cat photo - 无关物体
        "expected": {
            "routes": ["shopping", "chitchat", "unknown"],
            "task_types": ["shopping", "chitchat", "unknown"],
            "require_answer": True,
            "reference_answer": "图片内容跟商品无关，礼貌说明未找到同款或引导用户提供其他信息。",
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-019", "scenario": "multimodal_shopping", "tags": ["image", "adversarial", "multi_product"],
        "input": "帮我找图里这些商品",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1583947215259-38e31be8751f?w=800"},  # multiple cosmetics
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "reference_answer": "针对图中主要商品做检索，允许无法精确对应多个商品的降级说明。",
            "max_latency_ms": 20000,
        },
    },
    {
        "id": "img-020", "scenario": "multimodal_shopping", "tags": ["image", "adversarial", "low_quality"],
        "input": "找类似这个",
        "request": {"image_url": f"{UNSPLASH_BASE}/photo-1610384104075-e05c8cf200c3?w=200"},  # 小尺寸 low-quality
        "expected": {
            "routes": ["shopping"], "task_types": ["shopping"],
            "required_tools": ["search_multimodal_v1"],
            "require_product_cards": True,
            "max_latency_ms": 20000,
        },
    },
]


def main():
    # 读现有 130 条
    lines = DATASET.read_text(encoding="utf-8").splitlines()
    header = []
    keep_cases = []
    for l in lines:
        if not l.strip():
            continue
        if l.startswith("#"):
            header.append(l)
            continue
        c = json.loads(l)
        # 移除所有旧的 multimodal_shopping case（img-*）
        if c.get("scenario") == "multimodal_shopping":
            continue
        keep_cases.append(c)

    print(f"保留其他场景: {len(keep_cases)} 条")
    print(f"新增 multimodal: {len(MULTIMODAL_CASES)} 条")

    # 合并
    all_cases = keep_cases + MULTIMODAL_CASES

    # 保存
    with DATASET.open("w", encoding="utf-8") as f:
        for h in header:
            f.write(h + "\n")
        for c in all_cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    from collections import Counter
    by_sce = Counter(c["scenario"] for c in all_cases)
    with_grades = sum(1 for c in all_cases if "retrieval_grades" in c.get("expected", {}))
    print(f"\n最终 agent_golden_cases: {len(all_cases)} 条")
    for s, n in sorted(by_sce.items()):
        print(f"  {s:22}: {n}")
    print(f"  retrieval_grades 标注: {with_grades}")


if __name__ == "__main__":
    main()
