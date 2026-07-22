"""Small, auditable category normalization for Shopping retrieval."""
from __future__ import annotations

from typing import Optional


# Catalog-backed aliases. Unknown phrases remain semantic query text rather
# than becoming an exact Milvus filter.
_CATEGORY_ALIASES: tuple[tuple[str, str], ...] = (
    ("真无线耳机", "真无线耳机"),
    ("蓝牙耳机", "真无线耳机"),
    ("碳板跑鞋", "跑步鞋"),
    ("跑步鞋", "跑步鞋"),
    ("运动鞋", "跑步鞋"),
    ("跑鞋", "跑步鞋"),
    ("篮球鞋", "篮球鞋"),
    ("方便面", "方便食品"),
    ("速食", "方便食品"),
    ("黑咖啡", "咖啡"),
    ("咖啡", "咖啡"),
    ("气泡水", "碳酸饮料"),
    ("苏打水", "碳酸饮料"),
    ("功能饮料", "功能饮料"),
    ("能量饮料", "功能饮料"),
    ("防晒霜", "防晒"),
    ("防晒乳", "防晒"),
    ("防晒", "防晒"),
    ("抗初老精华", "精华"),
    ("抗老精华", "精华"),
    ("淡纹精华", "精华"),
    ("紧致精华", "精华"),
    ("精华", "精华"),
    ("面霜", "面霜"),
    ("洁面", "洁面"),
    ("洗面奶", "洁面"),
    ("粉底液", "粉底液"),
    ("平板", "平板电脑"),
    ("笔记本", "笔记本电脑"),
    ("电脑", "笔记本电脑"),
    ("手机", "智能手机"),
    ("iphone", "智能手机"),
)


def normalize_product_category(value: str | None) -> Optional[str]:
    """Return one exact catalog sub-category when the mapping is safe."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    for alias, canonical in _CATEGORY_ALIASES:
        if alias in text:
            return canonical
    return None
