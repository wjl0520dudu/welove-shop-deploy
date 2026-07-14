# 多模态商品检索 — 开发文档

> **状态**：待开发  
> **创建**：2026-07-14  
> **目标**：在 `product_mm_v2` 新 collection 上构建多模态检索能力，对比 3 个图文混合接口，选出最优方案上线。

---

## 目录

- [§0 背景与动机](#0-背景与动机)
- [§1 系统架构](#1-系统架构)
- [§2 Collection Schema：product_mm_v2](#2-collection-schema-product_mm_v2)
- [§3 文本向量化优化](#3-文本向量化优化)
- [§4 多模态 Embedding API](#4-多模态-embedding-api)
- [§5 三个图文检索接口](#5-三个图文检索接口)
- [§6 RRF 去重融合](#6-rrf-去重融合)
- [§7 多模态 Rerank](#7-多模态-rerank)
- [§8 数据灌入脚本](#8-数据灌入脚本)
- [§9 评测方案](#9-评测方案)
- [§10 实施步骤](#10-实施步骤)
- [§11 环境变量](#11-环境变量)
- [§12 文件清单](#12-文件清单)

---

## §0 背景与动机

### 0.1 当前状态

- 商品检索在 `product_mm_collection` 上，只有 `text_dense_vector`（text-embedding-v4, 1024维）+ BM25（Milvus 内置 Function）
- `multimodal_vector` 字段已建但灌零向量占位，**未启用**
- 检索模式：纯文本 hybrid（dense + BM25 + RRFRanker），无图片检索能力
- 文本向量化的 `text` 字段格式：`title + title(重复) + brand + category + sub_category + tags + description`（纯空格拼接，无字段标签）

### 0.2 目标

1. **文本向量化优化**：去重复 title + 加字段标签，提升文本语义匹配质量
2. **图片检索**：支持以图搜图
3. **图文混合检索**：对比三种接口，选出最优方案
4. **评测驱动决策**：LLM-as-Judge 全自动评测，数据说话

### 0.3 为什么新建 collection

- 旧 `product_mm_collection` 保持不动（线上服务不受影响）
- 新 `product_mm_v2` 独立建库，方便 A/B 对比
- 评测完确认新方案优于旧方案后再切

---

## ⚠️ 开发范围声明（给 GPT 5.5 or 开发者的你）

### 你需要做的（Step 1-5）

| Step | 产出 | 说明 |
|------|------|------|
| **Step 1** | `ai-service/shopping/vector_store_v2.py` | 新建 `ProductMilvusStoreV2` 类，管理 `product_mm_v2` collection 的创建、索引、upsert、四路检索 |
| **Step 2** | `ai-service/rag/multimodal_embeddings.py` | 封装 `embed_image()` / `embed_fusion()` / `multimodal_rerank()` |
| **Step 3** | 修改 `ai-service/rag/embeddings.py` | 新增 `_build_search_text_v2()` 函数 |
| **Step 4** | `ai-service/shopping/multimodal_search.py` | 实现三个图文检索接口（①三路 ②四路+rerank ③四路+WeightedRanker）+ RRF 去重融合 |
| **Step 5** | `ai-service/scripts/sync_products_to_milvus_v2.py` | 数据灌入脚本（PG → Milvus v2） |

### 你**不需要**做的

| 事项 | 原因 |
|------|------|
| ❌ 评测脚本（`eval_multimodal_retrieval.py`） | 由我来写，避免你跑 LLM 调用浪费 token |
| ❌ Mock 查询数据 | 由我来准备 |
| ❌ 跑实际评测 | 由我来执行 |
| ❌ 修改 `product_mm_collection`（旧 collection） | 保持不动，线上服务不受影响 |
| ❌ 修改纯文本检索链路 | 现有 hybrid_search 不动 |
| ❌ 跑 `scripts/sync_products_to_milvus_v2.py` 灌数据 | 由我来跑，灌数据涉及多模态 API 调用有费用 |

### 代码质量要求

- 复用现有 `ProductMilvusStore` 的 filter 表达式（`build_milvus_filter_expr`）、连接管理、RRFRanker 等底层逻辑，不要重写
- 多模态 API 调用失败时**降级不抛异常**（参考现有 `reranker.py` 的降级策略）
- 所有新增代码用跟现有项目一致的风格：中文注释 + `from __future__ import annotations` + logging

---

## §1 系统架构

### 1.1 检索路径总览

```
                         用户输入
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
         纯文本           纯图片          图文混合
            │               │               │
            ▼               ▼               ▼
   现有 hybrid_search   image_vector    ┌─ 接口① 三路 + RRF + vl-rerank
   (BM25+dense+rerank)   单路检索      ├─ 接口② 四路 + RRF + vl-rerank
       不动！              不动！       └─ 接口③ 四路 + RRF + WeightedRanker
                                          
                                         三者对比评测 → 选最优
```

> **纯文本路径已有 RRF**：现有 `hybrid_search()` 内部用 Milvus 内置 `RRFRanker(k=60)` 对 BM25 + text_dense 两路做 RRF 融合，然后送给 `qwen3-rerank` 精排。本次开发**不动**这条路径。
>
> **图文路径的 RRF**：图文多路（3 路或 4 路）在**应用层**做 RRF 去重融合，统一做完后再送精排，不再像纯文本那样先 RRF 再 rerank。详见 [§6](#6-rrf-去重融合)。

### 1.2 向量模型分工

| 用途 | 模型 | 维度 | 语义空间 |
|------|------|------|---------|
| 文本 Dense | text-embedding-v4 | 1024 | 纯文本空间 |
| 图片向量 | qwen3-vl-embedding | 2560（可截断） | 多模态统一空间 |
| 图文融合向量 | qwen3-vl-embedding (enable_fusion=True) | 2560（可截断） | 多模态统一空间 |
| BM25 | Milvus 内置 Function | 稀疏 | 无 |

> **关键认知**：v4 和 qwen3-vl-embedding 语义空间不兼容，即使同维度也不能交叉算相似度。因此融合只能走**结果级 RRF**，不能走向量级融合。

---

## §2 Collection Schema：product_mm_v2

### 2.1 与旧 collection 的差异

| 对比项 | product_mm_collection（旧） | product_mm_v2（新） |
|--------|---------------------------|---------------------|
| text 字段内容 | title×2 + brand + category + ... | 结构化标签格式（见 §3） |
| text_dense_vector | text-embedding-v4, 1024维 | text-embedding-v4, 1024维（不变） |
| image_vector | **无** | **新增** qwen3-vl-embedding, 2560维 |
| multimodal_vector | 零向量占位 | **启用** qwen3-vl-embedding fusion, 2560维 |
| text_sparse_vector | BM25 Function | BM25 Function（不变） |

### 2.2 完整字段定义

```python
# product_mm_v2 schema

from pymilvus import FieldSchema, DataType, Function, FunctionType

TEXT_DIM = 1024       # text-embedding-v4
IMAGE_DIM = 2560      # qwen3-vl-embedding（可配置截断到 1024）
MULTIMODAL_DIM = 2560 # qwen3-vl-embedding fusion（同上）

ANALYZER_PARAMS = {"type": "chinese"}  # jieba 中文分词

fields = [
    # ── 主键 ──
    FieldSchema(name="product_id", dtype=DataType.INT64, is_primary=True),

    # ── BM25 文本源（结构化标签格式，见 §3）──
    FieldSchema(
        name="text", dtype=DataType.VARCHAR, max_length=65535,
        enable_analyzer=True, analyzer_params=ANALYZER_PARAMS,
    ),

    # ── 四向量字段 ──
    FieldSchema(name="text_dense_vector", dtype=DataType.FLOAT_VECTOR, dim=TEXT_DIM),
    FieldSchema(name="text_sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),  # BM25 Function 自动生成
    FieldSchema(name="image_vector", dtype=DataType.FLOAT_VECTOR, dim=IMAGE_DIM),        # ★ 新增
    FieldSchema(name="multimodal_vector", dtype=DataType.FLOAT_VECTOR, dim=MULTIMODAL_DIM), # ★ 启用

    # ── 展示字段（避免回 PG）──
    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=256),
    FieldSchema(name="brand", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="image_url", dtype=DataType.VARCHAR, max_length=512),
    FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=2048),

    # ── 过滤 + 排序字段 ──
    FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="sub_category", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=512),
    FieldSchema(name="base_price", dtype=DataType.FLOAT),
    FieldSchema(name="rating", dtype=DataType.FLOAT),
    FieldSchema(name="sales_count", dtype=DataType.INT64),
    FieldSchema(name="review_count", dtype=DataType.INT64),
    FieldSchema(name="status", dtype=DataType.INT8),  # 1=在售 0=下架
]
```

### 2.3 BM25 Function

```python
# 跟旧 collection 完全一致，从 text 字段自动生成 text_sparse_vector
bm25_function = Function(
    name="bm25",
    input_field_names=["text"],
    output_field_names=["text_sparse_vector"],
    function_type=FunctionType.BM25,
)
```

### 2.4 索引配置

```python
# text_dense_vector：跟旧 collection 一致
collection.create_index("text_dense_vector", {
    "index_type": "AUTOINDEX", "metric_type": "IP"
})

# text_sparse_vector：跟旧 collection 一致
collection.create_index("text_sparse_vector", {
    "index_type": "SPARSE_INVERTED_INDEX",
    "metric_type": "BM25",
    "params": {"inverted_index_algo": "DAAT_MAXSCORE", "bm25_k1": 1.2, "bm25_b": 0.75},
})

# image_vector：★ 新增
collection.create_index("image_vector", {
    "index_type": "AUTOINDEX", "metric_type": "IP"
})

# multimodal_vector：★ 新增
collection.create_index("multimodal_vector", {
    "index_type": "AUTOINDEX", "metric_type": "IP"
})
```

### 2.5 检索返回字段

```python
OUTPUT_FIELDS = [
    "product_id", "title", "brand", "image_url", "description",
    "category", "sub_category", "tags",
    "base_price", "rating", "sales_count", "review_count", "status",
]
```

---

## §3 文本向量化优化

### 3.1 旧格式（问题）

```
安热沙小金瓶防晒 安热沙小金瓶防晒 安热沙 美妆护肤 防晒 防晒,隔离,清爽 轻薄乳液质地，SPF50+ PA++++...
```

- title 重复两次（对 BM25 有意义，对 dense 冗余）
- 无字段标签（embedding 模型不知道哪段是品牌、哪段是品类）
- tags 是裸逗号串

### 3.2 新格式（`_build_search_text_v2`）

```
[标题] 安热沙小金瓶防晒
[品牌] 安热沙
[品类] 美妆护肤
[子品类] 防晒
[标签] 防晒, 隔离, 清爽
[描述] 轻薄乳液质地，SPF50+ PA++++，适合油皮混油皮...
```

改动点：
- **去掉 title 重复**（dense 向量不需要）
- **字段加 `[标签]` 前缀**（帮助 embedding 模型理解语义角色）
- **换行分隔**（比空格更清晰）
- **缺失字段跳过**（不同产品字段不一致，有空就跳过）

### 3.3 实现代码

```python
def _build_search_text_v2(p: dict) -> str:
    """构建结构化文本（BM25 + Dense 共用）。

    格式：每行 [字段名] 值，缺失字段跳过。
    """
    field_map = {
        "标题":   p.get("title"),
        "品牌":   p.get("brand"),
        "品类":   p.get("category"),
        "子品类": p.get("sub_category"),
        "标签":   p.get("tags"),
        "描述":   p.get("description"),
    }
    lines = []
    for label, value in field_map.items():
        v = str(value).strip() if value else ""
        if v:
            lines.append(f"[{label}] {v}")
    return "\n".join(lines)
```

### 3.4 注意事项

- `text` 字段同时也用于 BM25 分词，加 `[标题]` 等标签对 BM25 的影响是：这些标签词会被 jieba 分词但几乎不在查询中出现，对 BM25 匹配质量影响极小
- 如果后续评测发现标签词干扰了 BM25，可以 BM25 和 Dense **分拆 text 源**（BM25 保持旧格式，Dense 用新格式），但当前阶段先用同一个 text 简化实现

---

## §4 多模态 Embedding API

### 4.1 业务空间端点

多模态相关 API 使用业务空间专属端点（与文本 rerank 的公共端点不同）：

```python
import dashscope
dashscope.base_http_api_url = "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1"
```

`{WorkspaceId}` 从百炼控制台获取，建议放 `.env` 里。

### 4.2 纯图片 Embedding → image_vector

```python
from dashscope import MultiModalEmbedding

resp = MultiModalEmbedding.call(
    model="qwen3-vl-embedding",
    input=[{"image": image_url}],  # 单张图片 URL
)
# → resp.output["embeddings"][0]["embedding"]  # 2560维 list[float]
```

### 4.3 图文融合 Embedding → multimodal_vector

关键参数 `enable_fusion=True`，将图片和文本融合成**一个**向量：

```python
resp = MultiModalEmbedding.call(
    model="qwen3-vl-embedding",
    input=[
        {"text": "结构化标签文本（同 §3.2 格式）"},
        {"image": image_url},
    ],
    enable_fusion=True,  # ★ 必须！否则返回各自的独立向量
    # dimension=1024,    # 可选，默认 2560
)
# → resp.output["embeddings"][0]["embedding"]  # 融合后的单向量
```

### 4.4 维度选择

| 选项 | 优点 | 缺点 |
|------|------|------|
| 2560（默认） | 信息量最大 | 内存/索引更大，跟 v4 的 1024 不对齐 |
| 1024（截断） | 跟 text_dense 同维度，索引一致 | 信息压缩，可能损失精度 |

**建议先用 2560**，评测完如果精度差异不大再考虑截断到 1024 省资源。

### 4.5 批量调用

多模态 embedding 目前**没有明确的批量上限**，建议保守按单条调用，后续根据 API 文档调整。

---

## §5 三个图文检索接口

### 5.1 总览

```
图文混合查询(query_text, query_image_url)
        │
        ├── 接口① 三路融合
        │    text_dense + BM25 + image_vector
        │    → RRF 去重 → qwen3-vl-rerank
        │
        ├── 接口② 四路融合 + vl-rerank
        │    text_dense + BM25 + image_vector + multimodal_vector
        │    → RRF 去重 → qwen3-vl-rerank
        │
        └── 接口③ 四路融合 + WeightedRanker
             text_dense + BM25 + image_vector + multimodal_vector
             → RRF 去重 → WeightedRanker
```

### 5.2 接口①：三路 + RRF + vl-rerank

```python
async def search_multimodal_v1(
    query_text: str,
    query_image_url: str,
    top_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """
    三路融合：text_dense(v4) + BM25 + image(qwen3-vl)
    → 应用层 RRF 去重 → qwen3-vl-rerank 精排
    """
    # 1. query(文) → v4 → text_dense 检索
    query_vec_text = text_embeddings.embed_query(query_text)
    dense_results = text_dense_search(query_vec_text, top_k=top_k * 2, filters=filters)

    # 2. query(文) → BM25 检索
    bm25_results = bm25_search(query_text, top_k=top_k * 2, filters=filters)

    # 3. query(图) → qwen3-vl → image_vector 检索
    query_vec_image = multimodal_embed_image(query_image_url)
    image_results = image_vector_search(query_vec_image, top_k=top_k * 2, filters=filters)

    # 4. 三路 RRF 去重融合
    fused = rrf_fusion(
        [dense_results, bm25_results, image_results],
        k=60,  # RRF 平滑参数
    )

    # 5. qwen3-vl-rerank 精排
    candidates = fused[:top_k * 2]  # 取 RRF 前 N 送给 rerank
    reranked = multimodal_rerank(
        query_text=query_text,
        query_image_url=query_image_url,
        documents=candidates,
        top_n=top_k,
    )
    return reranked
```

### 5.3 接口②：四路 + RRF + vl-rerank

```python
async def search_multimodal_v2(
    query_text: str,
    query_image_url: str,
    top_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    """
    四路融合：①的三路 + multimodal_vector
    → 应用层 RRF 去重 → qwen3-vl-rerank 精排
    """
    # 前三路同接口① ...

    # 4. query(图+文) → qwen3-vl fusion → multimodal_vector 检索
    query_vec_multimodal = multimodal_embed_fusion(query_text, query_image_url)
    multimodal_results = multimodal_vector_search(query_vec_multimodal, top_k=top_k * 2, filters=filters)

    # 5. 四路 RRF 去重融合
    fused = rrf_fusion(
        [dense_results, bm25_results, image_results, multimodal_results],
        k=60,
    )

    # 6. qwen3-vl-rerank 精排
    candidates = fused[:top_k * 2]
    reranked = multimodal_rerank(
        query_text=query_text,
        query_image_url=query_image_url,
        documents=candidates,
        top_n=top_k,
    )
    return reranked
```

### 5.4 接口③：四路 + RRF + WeightedRanker

```python
async def search_multimodal_v3(
    query_text: str,
    query_image_url: str,
    top_k: int = 10,
    filters: dict | None = None,
    weights: tuple[float, float, float, float] = (0.3, 0.2, 0.3, 0.2),
) -> list[dict]:
    """
    四路融合 + WeightedRanker（不用 rerank）
    weights: (text_dense, bm25, image, multimodal) 权重
    """
    # 1-4. 四路检索同接口② ...

    # 5. 四路 RRF 去重融合
    fused = rrf_fusion(
        [dense_results, bm25_results, image_results, multimodal_results],
        k=60,
    )

    # 6. WeightedRanker（不用 vl-rerank）
    weighted = weighted_rerank(fused, weights=weights)
    return weighted[:top_k]
```

### 5.5 对比维度

| 接口 | 路数 | 精排 | 对比目的 |
|------|------|------|---------|
| ① | 3 路 | qwen3-vl-rerank | 基线：multimodal 向量有没有增量？ |
| ② | 4 路 | qwen3-vl-rerank | 跟①比：多一路 multimodal 是否提升？ |
| ③ | 4 路 | WeightedRanker | 跟②比：vl-rerank vs WeightedRanker 哪个好？ |

---

## §6 RRF 去重融合

### 6.1 为什么应用层做 RRF

- Milvus 内置 RRFRanker 只支持两路融合（dense + sparse）
- 三路/四路需要应用层统一 RRF
- 不同路可能返回相同 product_id，需要先去重再 RRF

### 6.2 实现

```python
def rrf_fusion(
    result_groups: list[list[dict]],
    k: int = 60,
    id_field: str = "product_id",
    score_field: str = "score",
) -> list[dict]:
    """
    多路结果 RRF 融合 + 去重。

    Args:
        result_groups: 各路检索结果，每组是按分数降序的列表
        k: RRF 平滑参数（默认 60，跟 Milvus 内置一致）
        id_field: 唯一标识字段名
        score_field: 各路结果中的分数字段名（用于去重时保留最高分）

    Returns:
        按 RRF 分数降序排列的融合结果
    """
    # 1. 去重：同一 product_id 出现多次，保留原始分数最高的
    deduped: dict[str, dict] = {}
    for group in result_groups:
        for item in group:
            pid = item[id_field]
            if pid not in deduped or item.get(score_field, 0) > deduped[pid].get(score_field, 0):
                deduped[pid] = item

    # 2. RRF 计分
    rrf_scores: dict[str, float] = {}
    for group in result_groups:
        for rank, item in enumerate(group):
            pid = item[id_field]
            rrf_scores[pid] = rrf_scores.get(pid, 0) + 1.0 / (k + rank + 1)

    # 3. 按 RRF 分数排序
    sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
    result = []
    for pid in sorted_ids:
        deduped[pid]["rrf_score"] = rrf_scores[pid]
        result.append(deduped[pid])

    return result
```

---

## §7 多模态 Rerank

### 7.1 API 调用

```python
import dashscope
from http import HTTPStatus

# 业务空间端点
dashscope.base_http_api_url = "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1"

def multimodal_rerank(
    query_text: str,
    query_image_url: str | None,
    documents: list[dict],
    top_n: int = 10,
) -> list[dict]:
    """
    qwen3-vl-rerank 多模态精排。

    Args:
        query_text: 查询文本
        query_image_url: 查询图片（可选，纯文本查询时传 None）
        documents: 候选商品列表，每个 dict 至少包含 title/description/image_url
        top_n: 返回前 N 条

    Returns:
        按 relevance_score 降序的 documents 子集
    """
    # 构建 query
    query: dict = {"text": query_text}
    if query_image_url:
        query["image"] = query_image_url

    # 构建 documents（图文混合）
    doc_inputs = []
    for doc in documents:
        doc_item = {}
        # 文本：标题 + 描述
        text_parts = [doc.get("title", ""), doc.get("description", "")]
        doc_item["text"] = " ".join(p for p in text_parts if p)
        # 图片：商品主图
        if doc.get("image_url"):
            doc_item["image"] = doc["image_url"]
        doc_inputs.append(doc_item)

    resp = dashscope.TextReRank.call(
        model="qwen3-vl-rerank",
        query=query,
        documents=doc_inputs,
        top_n=top_n,
        return_documents=False,
    )

    if resp.status_code != HTTPStatus.OK:
        # 降级：返回原顺序
        return documents[:top_n]

    # 解析结果
    results = (resp.output or {}).get("results") or []
    reranked = []
    for r in results:
        idx = r.get("index")
        score = r.get("relevance_score")
        if idx is not None and score is not None:
            doc = documents[int(idx)].copy()
            doc["rerank_score"] = float(score)
            reranked.append(doc)

    return reranked[:top_n]
```

### 7.2 WeightedRanker（接口③用）

```python
def weighted_rerank(
    candidates: list[dict],
    weights: tuple[float, ...] = (0.3, 0.2, 0.3, 0.2),
) -> list[dict]:
    """
    对 RRF 融合后的结果按原始分数加权重排。

    candidates 中每个 item 应有字段标明来源，加权公式：
      final_score = w1 * dense_score + w2 * bm25_score + w3 * image_score + w4 * multimodal_score
    缺失的分数项填 0。
    """
    for item in candidates:
        item["weighted_score"] = (
            weights[0] * item.get("dense_score", 0)
            + weights[1] * item.get("bm25_score", 0)
            + weights[2] * item.get("image_score", 0)
            + weights[3] * item.get("multimodal_score", 0)
        )
    return sorted(candidates, key=lambda x: x["weighted_score"], reverse=True)
```

---

## §8 数据灌入脚本

### 8.1 数据源

从 PostgreSQL `product` 表 JOIN `category` 表读取，跟现有 `sync_products_pg_to_milvus.py` 一致。

### 8.2 灌入流程

```
PG product 表
    │
    ├── 文本字段 → _build_search_text_v2() → text 字段
    ├── text → text-embedding-v4 → text_dense_vector
    ├── image_url → qwen3-vl-embedding(image) → image_vector
    └── image_url + 结构化标签 → qwen3-vl-embedding(fusion) → multimodal_vector
            │
            ▼
    Milvus product_mm_v2 collection
```

### 8.3 每条商品的向量化步骤

```python
async def build_product_mm_v2_row(product: dict) -> dict:
    """
    product: PG 查询结果，包含 title/brand/category/sub_category/tags/
             description/image_url/base_price/rating/...
    """
    # 1. 结构化文本
    text = _build_search_text_v2(product)

    # 2. text_dense_vector（v4, 1024维）
    text_dense = text_embeddings.embed_query(text)

    # 3. image_vector（qwen3-vl, 2560维）
    image_url = product.get("image_url")
    if image_url:
        image_vec = multimodal_embed_image(image_url)
    else:
        image_vec = [0.0] * IMAGE_DIM  # 无图商品填零向量

    # 4. multimodal_vector（qwen3-vl fusion, 2560维）
    if image_url:
        # 图文融合向量：结构化标签文本 + 图片
        multimodal_vec = multimodal_embed_fusion(text, image_url)
    else:
        multimodal_vec = [0.0] * MULTIMODAL_DIM  # 无图商品填零向量

    return {
        "product_id": product["id"],
        "text": text,
        "text_dense_vector": text_dense,
        "image_vector": image_vec,
        "multimodal_vector": multimodal_vec,
        "title": str(product.get("title") or "")[:256],
        "brand": str(product.get("brand") or "")[:64],
        "image_url": str(product.get("image_url") or "")[:512],
        "description": str(product.get("description") or "")[:2048],
        "category": str(product.get("category") or "")[:64],
        "sub_category": str(product.get("sub_category") or "")[:64],
        "tags": str(product.get("tags") or "")[:512],
        "base_price": float(product.get("base_price") or 0),
        "rating": float(product.get("rating") or 0),
        "sales_count": int(product.get("sales_count") or 0),
        "review_count": int(product.get("review_count") or 0),
        "status": int(product.get("status") or 1),
    }
```

### 8.4 脚本参数

```bash
# 全量同步（清空 collection 后重新灌入）
python scripts/sync_products_to_milvus_v2.py --mode full

# 增量同步（按 update_time）
python scripts/sync_products_to_milvus_v2.py --mode incremental

# 单商品同步（调试用）
python scripts/sync_products_to_milvus_v2.py --mode one --product-id 42
```

### 8.5 注意事项

- 多模态 embedding API 可能有 QPS 限制，脚本需要加限流（建议 sleep 0.1-0.2s/条）
- 无图商品（image_url 为空）的 image_vector 和 multimodal_vector 填零向量，检索时这些商品只在纯文本路出现
- 嵌入调用失败需要重试（至少 3 次），重试失败记录日志但**不阻塞整体流程**（该商品跳过多模态向量，文本路仍可用）

---

## §9 评测方案

### 9.1 评测指标

| 指标 | 含义 | 计算方式 |
|------|------|---------|
| **NDCG@5** | 前 5 个排序质量（考虑位置权重） | 标准 NDCG |
| **NDCG@10** | 前 10 个排序质量 | 标准 NDCG |
| **Recall@5** | 前 5 个召回率（相关商品有没有被找到） | 相关命中数 / 总相关数 |
| **Recall@10** | 前 10 个召回率 | 同上 |
| **MRR** | 第一个相关商品的平均倒数排名 | 1/第一个相关商品的位置 |
| **Hit@1** | 第一位命中率 | 最相关商品在不在第一位 |

差异 > 0.05 才认为有意义。

### 9.2 Mock 查询生成

从库里随机抽取 20-30 个商品，用它们的标题 + 图片作为素材，改写为自然语言查询：

```python
# 示例 mock 查询
MOCK_QUERIES = [
    {
        "query_text": "推荐一款清爽的防晒，适合油皮使用",
        "query_image_url": "https://...安热沙小金瓶主图.jpg",
        # 从哪个商品改写而来（用于验证召回）
        "source_product_id": 1,
    },
    {
        "query_text": "有没有跟这个差不多的跑鞋，但预算在 500 以内",
        "query_image_url": "https://...Nike跑鞋主图.jpg",
        "source_product_id": 25,
    },
    # ... 共 20-30 条
]
```

### 9.3 LLM-as-Judge 打分

每条查询跑 3 个接口，每个接口返回 top 10，交给 LLM 判断每条结果的相关性：

```python
JUDGE_PROMPT = """
你是一个电商商品相关性评估专家。请根据用户的查询（文本+图片），判断每个召回商品的相关性。

## 用户查询
- 文本：{query_text}
- 图片：{query_image_url}

## 召回商品
{product_list}

## 打分标准
- 3 分：高度相关，完美匹配用户需求
- 2 分：相关，但有小差异（如品类对但品牌/价格不完全匹配）
- 1 分：勉强相关（如品类相似但核心需求不匹配）
- 0 分：不相关

请对每个商品独立打分，返回 JSON：
{{"scores": [{{"product_id": 1, "score": 3, "reason": "..."}}, ...]}}
"""
```

### 9.4 评测脚本

```python
# scripts/eval_multimodal_retrieval.py

async def main():
    queries = load_mock_queries()  # 20-30 条
    interfaces = {
        "v1_three_path": search_multimodal_v1,
        "v2_four_path_rerank": search_multimodal_v2,
        "v3_four_path_weighted": search_multimodal_v3,
    }

    all_results = {}
    for name, fn in interfaces.items():
        print(f"\n{'='*50}")
        print(f"评测接口: {name}")
        print(f"{'='*50}")

        # 每条 query 跑 3 次取平均
        query_scores = []
        for query in queries:
            scores = []
            for run in range(3):
                results = await fn(query["query_text"], query["query_image_url"])
                judged = await llm_judge(query, results)
                scores.append(judged)
            # 平均分数
            avg = average_scores(scores)
            query_scores.append(avg)

        # 计算指标
        metrics = compute_metrics(query_scores)
        all_results[name] = metrics

    # 输出对比表
    print_comparison_table(all_results)
```

### 9.5 评测输出格式

```
接口                   NDCG@5   NDCG@10  Recall@5  Recall@10  MRR     Hit@1
─────────────────────────────────────────────────────────────────────────────
① 三路+vl-rerank        0.723    0.781    0.654     0.782      0.812   0.650
② 四路+vl-rerank        0.741    0.795    0.668     0.790      0.825   0.667
③ 四路+WeightedRanker   0.698    0.762    0.632     0.758      0.788   0.617
─────────────────────────────────────────────────────────────────────────────
最优                    ②        ②        ②         ②          ②       ②
```

---

## §10 实施步骤

### Step 1：新建 `product_mm_v2` collection

**产出**：`ai-service/shopping/vector_store_v2.py`

- 实现 `ProductMilvusStoreV2` 类
- 复用现有 `ProductMilvusStore` 的 filter 表达式、连接管理等底层逻辑
- 新增 `image_vector_search()` 和 `multimodal_vector_search()` 方法
- 纯文本检索不受影响（走旧 collection）

### Step 2：多模态 Embedding 封装

**产出**：`ai-service/rag/multimodal_embeddings.py`

- 封装 `embed_image(image_url)` → 2560维
- 封装 `embed_fusion(text, image_url)` → 2560维（enable_fusion=True）
- 封装 `multimodal_rerank(query_text, query_image_url, documents, top_n)`
- 失败降级策略（同现有 rerank：不抛异常，返回原顺序）

### Step 3：文本向量化优化

**产出**：修改 `_build_search_text` → `_build_search_text_v2`

- 去重 title + 加 `[字段名]` 标签
- 确保 `product_mm_v2` 用新格式，`product_mm_collection` 保持旧格式

### Step 4：三个接口实现

**产出**：`ai-service/shopping/multimodal_search.py`

- 接口①：三路 + RRF + vl-rerank
- 接口②：四路 + RRF + vl-rerank
- 接口③：四路 + RRF + WeightedRanker
- RRF 去重融合函数（应用层）

### Step 5：数据灌入脚本

**产出**：`ai-service/scripts/sync_products_to_milvus_v2.py`

- 从 PG 读取全量商品
- 对每条商品：文本向量化 + 图片向量化 + 图文融合向量化
- 批量 upsert 到 `product_mm_v2`
- 支持 `--mode full/incremental/one`

### Step 6：评测脚本

**产出**：`ai-service/scripts/eval_multimodal_retrieval.py`

- Mock 20-30 条图文查询
- 调 3 个接口，每次跑 3 轮
- LLM-as-Judge 打分
- 输出对比表

### Step 7：跑评测 → 选最优 → 上线

- 评测算出的最优接口，替换旧检索链路
- 旧 `product_mm_collection` 保留作为回退

---

## §11 环境变量

需要在 `.env` 中新增/确认的配置：

```bash
# ── 多模态 Embedding ──
DASH_SCOPE_MULTI_MODAL_EMBEDDING_MODEL=qwen3-vl-embedding
DASH_SCOPE_MULTI_MODAL_RERANK_MODEL=qwen3-vl-rerank

# ── 业务空间端点（多模态 API 用，跟文本 rerank 的公共端点不同）──
DASHSCOPE_MAAS_BASE_URL=https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1

# ── 多模态向量维度（可选，默认 2560）──
MILVUS_IMAGE_DIM=2560
MILVUS_MULTIMODAL_DIM=2560

# ── 新 collection 名称 ──
MILVUS_PRODUCT_V2_COLLECTION=product_mm_v2
```

---

## §12 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `ai-service/shopping/vector_store_v2.py` | 新增 | `ProductMilvusStoreV2`，product_mm_v2 的 CRUD + 检索 |
| `ai-service/rag/multimodal_embeddings.py` | 新增 | 多模态 Embedding + Rerank 封装 |
| `ai-service/rag/embeddings.py` | 修改 | 新增 `_build_search_text_v2()` |
| `ai-service/shopping/multimodal_search.py` | 新增 | 三个图文检索接口 + RRF 融合 |
| `ai-service/scripts/sync_products_to_milvus_v2.py` | 新增 | 数据灌入脚本 |
| `ai-service/scripts/eval_multimodal_retrieval.py` | 新增 | 评测脚本 |
| `ai-service/core/config.py` | 修改 | 新增 v2 相关配置项 |
| `ai-service/.env` / `.env.example` | 修改 | 新增环境变量 |