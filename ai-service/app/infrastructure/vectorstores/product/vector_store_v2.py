"""ProductMilvusStoreV2 —— product_mm_v2 多模态实验 collection。

该模块不替换旧 `shopping.vector_store.ProductMilvusStore`，只服务多模态评测：
- text_dense_vector：DashScope text-embedding-v4，沿用 1024 维文本空间；
- text_sparse_vector：Milvus BM25 Function，从结构化 text 自动生成；
- image_vector：qwen3-vl-embedding 图片向量；
- multimodal_vector：qwen3-vl-embedding enable_fusion=True 图文融合向量。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    MilvusClient,
    connections,
)

from app.infrastructure.config import config
from app.infrastructure.retrieval.embeddings import get_embeddings
from app.infrastructure.vectorstores.product.vector_store import _ANALYZER_PARAMS, build_milvus_filter_expr

logger = logging.getLogger("ai-service.shopping.vector_store_v2")


def _build_fields_v2(text_dim: int, image_dim: int, multimodal_dim: int) -> list[FieldSchema]:
    """product_mm_v2 schema。"""
    return [
        FieldSchema(name="product_id", dtype=DataType.INT64, is_primary=True),
        FieldSchema(
            name="text",
            dtype=DataType.VARCHAR,
            max_length=65535,
            enable_analyzer=True,
            analyzer_params=_ANALYZER_PARAMS,
        ),
        FieldSchema(name="text_dense_vector", dtype=DataType.FLOAT_VECTOR, dim=text_dim),
        FieldSchema(name="text_sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema(name="image_vector", dtype=DataType.FLOAT_VECTOR, dim=image_dim),
        FieldSchema(name="multimodal_vector", dtype=DataType.FLOAT_VECTOR, dim=multimodal_dim),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="brand", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="image_url", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="sub_category", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="base_price", dtype=DataType.FLOAT),
        FieldSchema(name="rating", dtype=DataType.FLOAT),
        FieldSchema(name="sales_count", dtype=DataType.INT64),
        FieldSchema(name="review_count", dtype=DataType.INT64),
        FieldSchema(name="status", dtype=DataType.INT8),
    ]


INSERT_FIELDS_V2 = [
    "product_id", "text",
    "text_dense_vector", "image_vector", "multimodal_vector",
    "title", "brand", "image_url", "description",
    "category", "sub_category", "tags",
    "base_price", "rating", "sales_count", "review_count", "status",
]

OUTPUT_FIELDS_V2 = [
    "product_id",
    "title", "brand", "image_url", "description",
    "category", "sub_category", "tags",
    "base_price", "rating", "sales_count", "review_count", "status",
]

# 兼容测试/脚本里和旧 store 类似的命名习惯。
INSERT_FIELDS = INSERT_FIELDS_V2
OUTPUT_FIELDS = OUTPUT_FIELDS_V2


def _fit_vector(value: Any, dim: int) -> list[float]:
    if not isinstance(value, list):
        return [0.0] * dim
    out = [float(x or 0.0) for x in value[:dim]]
    if len(out) < dim:
        out.extend([0.0] * (dim - len(out)))
    return out


class ProductMilvusStoreV2:
    """product_mm_v2 collection 封装。"""

    def __init__(self, collection_name: Optional[str] = None):
        self.collection_name = collection_name or config.MILVUS_PRODUCT_V2_COLLECTION
        self.milvus_url = config.MILVUS_URL
        self.text_dim = int(config.MILVUS_DENSE_DIM)
        self.image_dim = int(config.MILVUS_IMAGE_DIM)
        self.multimodal_dim = int(config.MILVUS_MULTIMODAL_DIM)
        self.store: MilvusClient | None = None
        self._connect()

    # ── 连接 + 建表 + 建索引 ─────────────────────────────────
    def _connect(self) -> None:
        connections.connect(uri=self.milvus_url)
        milvus_client = MilvusClient(uri=self.milvus_url)
        self.store = milvus_client

        if milvus_client.has_collection(self.collection_name):
            logger.info("商品 v2 collection %s 已存在，跳过建表", self.collection_name)
            Collection(self.collection_name).load()
            return

        schema = CollectionSchema(
            _build_fields_v2(
                text_dim=self.text_dim,
                image_dim=self.image_dim,
                multimodal_dim=self.multimodal_dim,
            ),
            description="商品多模态向量库 v2（text_dense + BM25 + image + fusion）",
        )
        schema.add_function(Function(
            name="bm25_text_to_sparse",
            input_field_names=["text"],
            output_field_names=["text_sparse_vector"],
            function_type=FunctionType.BM25,
        ))

        collection = Collection(
            name=self.collection_name,
            schema=schema,
            consistency_level="Strong",
        )
        collection.create_index(
            "text_dense_vector",
            {"index_type": "AUTOINDEX", "metric_type": "IP"},
        )
        collection.create_index(
            "text_sparse_vector",
            {
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "BM25",
                "params": {"inverted_index_algo": "DAAT_MAXSCORE", "bm25_k1": 1.2, "bm25_b": 0.75},
            },
        )
        collection.create_index(
            "image_vector",
            {"index_type": "AUTOINDEX", "metric_type": "IP"},
        )
        collection.create_index(
            "multimodal_vector",
            {"index_type": "AUTOINDEX", "metric_type": "IP"},
        )
        collection.load()
        logger.info(
            "商品 v2 collection %s 建表成功（text=%d image=%d multimodal=%d）",
            self.collection_name, self.text_dim, self.image_dim, self.multimodal_dim,
        )

    # ── 结果转换 ────────────────────────────────────────────
    @staticmethod
    def _hit_to_dict(hit, score_field: str) -> Dict[str, Any]:
        entity = hit.entity
        base_price = float(entity.get("base_price") or 0)
        score = float(getattr(hit, "distance", 0.0) or 0.0)
        source_map = {
            "dense": "text_dense",
            "sparse": "bm25",
            "bm25": "bm25",
            "image": "image",
            "multimodal": "multimodal",
        }
        source = source_map.get(score_field, score_field)
        item: Dict[str, Any] = {
            "product_id": int(entity.get("product_id") or 0),
            "title": entity.get("title", "") or "",
            "brand": entity.get("brand", "") or "",
            "price": base_price,
            "base_price": base_price,
            "image_url": entity.get("image_url", "") or "",
            "rating": float(entity.get("rating") or 0),
            "review_count": int(entity.get("review_count") or 0),
            "sales_count": int(entity.get("sales_count") or 0),
            "category": entity.get("category", "") or "",
            "sub_category": entity.get("sub_category", "") or "",
            "tags": entity.get("tags", "") or "",
            "description": entity.get("description", "") or "",
            "status": int(entity.get("status") or 0),
            "score": score,
            "distance": score,
            "recall_sources": [source] if source else [],
        }
        if score_field == "dense":
            item["dense_score"] = score
        elif score_field in ("sparse", "bm25"):
            item["bm25_score"] = score
            item["sparse_score"] = score
        elif score_field == "image":
            item["image_score"] = score
        elif score_field == "multimodal":
            item["multimodal_score"] = score
        return item

    # ── 写入商品 ────────────────────────────────────────────
    def upsert_rows(self, rows: List[Dict[str, Any]]) -> int:
        """批量写入已经完成向量化的 v2 行。"""
        if not rows:
            return 0

        payload = {
            "product_id": [int(p["product_id"]) for p in rows],
            "text": [str(p.get("text") or "")[:65535] for p in rows],
            "text_dense_vector": [_fit_vector(p.get("text_dense_vector"), self.text_dim) for p in rows],
            "image_vector": [_fit_vector(p.get("image_vector"), self.image_dim) for p in rows],
            "multimodal_vector": [
                _fit_vector(p.get("multimodal_vector"), self.multimodal_dim) for p in rows
            ],
            "title": [str(p.get("title") or "")[:256] for p in rows],
            "brand": [str(p.get("brand") or "")[:64] for p in rows],
            "image_url": [str(p.get("image_url") or "")[:512] for p in rows],
            "description": [str(p.get("description") or "")[:2048] for p in rows],
            "category": [str(p.get("category") or "")[:64] for p in rows],
            "sub_category": [str(p.get("sub_category") or "")[:64] for p in rows],
            "tags": [str(p.get("tags") or "")[:512] for p in rows],
            "base_price": [float(p.get("base_price") or p.get("price") or 0) for p in rows],
            "rating": [float(p.get("rating") or 0) for p in rows],
            "sales_count": [int(p.get("sales_count") or 0) for p in rows],
            "review_count": [int(p.get("review_count") or 0) for p in rows],
            "status": [int(p.get("status") if p.get("status") is not None else 1) for p in rows],
        }

        collection = Collection(self.collection_name)
        collection.upsert([payload[f] for f in INSERT_FIELDS_V2])
        collection.flush()
        return len(rows)

    def upsert_products(self, rows: List[Dict[str, Any]]) -> int:
        """兼容旧同步脚本命名；v2 这里要求传入已向量化行。"""
        return self.upsert_rows(rows)

    def delete_by_product_id(self, product_id: int) -> int:
        collection = Collection(self.collection_name)
        collection.load()
        result = collection.delete(expr=f"product_id == {int(product_id)}")
        collection.flush()
        return result.delete_count if hasattr(result, "delete_count") else 0

    def stats(self) -> Dict[str, Any]:
        return {
            "provider": "milvus",
            "collection": self.collection_name,
            "text_dense_dim": self.text_dim,
            "image_dim": self.image_dim,
            "multimodal_dim": self.multimodal_dim,
        }

    # ── 检索：四路单独暴露给应用层 RRF ───────────────────────
    def dense_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        query_vec = get_embeddings().embed_query(query)
        return self.text_dense_search_by_vector(query_vec, filters=filters, top_k=top_k)

    def text_dense_search_by_vector(
        self,
        query_vector: list[float],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        collection = Collection(self.collection_name)
        collection.load()
        expr = build_milvus_filter_expr(filters)
        results = collection.search(
            [_fit_vector(query_vector, self.text_dim)],
            anns_field="text_dense_vector",
            param={"metric_type": "IP", "params": {}},
            limit=top_k,
            expr=expr,
            output_fields=OUTPUT_FIELDS_V2,
        )[0]
        return [self._hit_to_dict(h, "dense") for h in results]

    def bm25_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        collection = Collection(self.collection_name)
        collection.load()
        expr = build_milvus_filter_expr(filters)
        results = collection.search(
            [query],
            anns_field="text_sparse_vector",
            param={"metric_type": "BM25", "params": {}},
            limit=top_k,
            expr=expr,
            output_fields=OUTPUT_FIELDS_V2,
        )[0]
        return [self._hit_to_dict(h, "bm25") for h in results]

    def image_vector_search(
        self,
        query_vector: list[float],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        collection = Collection(self.collection_name)
        collection.load()
        expr = build_milvus_filter_expr(filters)
        results = collection.search(
            [_fit_vector(query_vector, self.image_dim)],
            anns_field="image_vector",
            param={"metric_type": "IP", "params": {}},
            limit=top_k,
            expr=expr,
            output_fields=OUTPUT_FIELDS_V2,
        )[0]
        return [self._hit_to_dict(h, "image") for h in results]

    def multimodal_vector_search(
        self,
        query_vector: list[float],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        collection = Collection(self.collection_name)
        collection.load()
        expr = build_milvus_filter_expr(filters)
        results = collection.search(
            [_fit_vector(query_vector, self.multimodal_dim)],
            anns_field="multimodal_vector",
            param={"metric_type": "IP", "params": {}},
            limit=top_k,
            expr=expr,
            output_fields=OUTPUT_FIELDS_V2,
        )[0]
        return [self._hit_to_dict(h, "multimodal") for h in results]


_product_store_v2_instance: ProductMilvusStoreV2 | None = None


def get_product_milvus_store_v2() -> ProductMilvusStoreV2:
    """懒加载单例 ProductMilvusStoreV2。"""
    global _product_store_v2_instance
    if _product_store_v2_instance is None:
        _product_store_v2_instance = ProductMilvusStoreV2()
    return _product_store_v2_instance
