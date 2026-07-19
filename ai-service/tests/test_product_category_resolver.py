from app.domain.shopping.category_resolver import normalize_product_category
from app.domain.shopping.multimodal_search import extract_explicit_product_filters


def test_catalog_aliases_normalize_to_existing_sub_categories():
    assert normalize_product_category("抗初老精华") == "精华"
    assert normalize_product_category("方便面") == "方便食品"
    assert normalize_product_category("碳板跑鞋") == "跑步鞋"
    assert normalize_product_category("真无线耳机") == "真无线耳机"


def test_unknown_or_broad_phrases_do_not_become_exact_filters():
    assert normalize_product_category("护肤品") is None
    assert normalize_product_category("提神饮品") is None


def test_multimodal_uses_the_same_category_normalization():
    assert extract_explicit_product_filters("找和图片中同类的方便面")["category"] == "方便食品"
    assert extract_explicit_product_filters("按图找类似的跑鞋")["category"] == "跑步鞋"
