# 三路商品向量库：本地核对与 Zilliz Cloud 导入

本手册对应多模态商品检索实验结论：生产只使用 **text dense + BM25 + image** 三路召回，RRF 融合后再进行 VL rerank。

## 1. 新 collection 结构

目标 collection 默认名：`product_multimodal_prod_v1`。

| 字段 | 类型 | 用途 |
|---|---|---|
| `product_id` | INT64 主键 | 商品唯一标识 |
| `text` | VARCHAR + analyzer | BM25 Function 输入 |
| `text_dense_vector` | FLOAT_VECTOR，1024 维 | 文本稠密检索 |
| `text_sparse_vector` | SPARSE_FLOAT_VECTOR | Milvus BM25 输出 |
| `image_vector` | FLOAT_VECTOR，2560 维 | 商品图片检索 |
| `title`、`brand`、`category`、`sub_category`、`tags`、`description` | VARCHAR | 结构化检索文本、商品展示与调试 |
| `image_url` | VARCHAR | OSS 商品图地址，返回商品卡片使用 |
| `base_price`、`rating`、`sales_count`、`review_count`、`status` | 标量字段 | 价格/状态筛选、排序与商品卡片 |

刻意不包含 `multimodal_vector`：该字段在 v2/v4/v5 实验路线中使用，但最终最优 v1 三路路线不使用它。

## 2. 先观察本地 `product_mm_v2`

在可运行 Python 虚拟环境的终端中：

```powershell
cd ai-service
python scripts/inspect_product_milvus_collection.py --collection product_mm_v2
```

输出会列出真实字段、维度、索引及实体数。预期可看到 `product_mm_v2` 有四个向量字段；生产三路 collection 只保留前三个实际需要的检索能力（文本稠密、BM25、图片）。

## 3. 本地预演（可选）

需要启动 PostgreSQL 和本地 Milvus；Redis、Nacos、Java 服务、AI FastAPI 均不需要。

```powershell
cd ai-service

# 仅验证 PG 商品读取与 Milvus 连接；不会创建 collection，不产生 embedding 费用
python scripts/prepare_product_three_path_collection.py `
  --collection product_multimodal_prod_v1_local `
  --dry-run

# 正式写入本地预演 collection：100 商品 × 文本 embedding + 图片 embedding
python scripts/prepare_product_three_path_collection.py `
  --collection product_multimodal_prod_v1_local `
  --batch-size 10
```

## 4. 导入 Zilliz Cloud

保持 PostgreSQL 可连接；将 Milvus 连接仅临时设为 Zilliz Cloud，避免把 token 写入 Git 或提交 `.env`：

```powershell
cd ai-service
$env:MILVUS_URL = "https://你的-zilliz-endpoint"
$env:MILVUS_TOKEN = "你的-zilliz-api-key"
$env:MILVUS_PRODUCT_THREE_PATH_COLLECTION = "product_multimodal_prod_v1"

# 先检查连接和商品读取
python scripts/prepare_product_three_path_collection.py `
  --collection product_multimodal_prod_v1 `
  --dry-run

# 确认后正式导入
python scripts/prepare_product_three_path_collection.py `
  --collection product_multimodal_prod_v1 `
  --batch-size 10

# 导入后只读核对 schema 与实体数
python scripts/inspect_product_milvus_collection.py `
  --collection product_multimodal_prod_v1
```

## 5. 云端三路检索 smoke 回归

生产 collection 没有 `multimodal_vector`，因此只运行最终选定的 v1 三路路线：

```powershell
python scripts/run_multimodal_retrieval_v1_experiment.py `
  --collection product_multimodal_prod_v1 `
  --routes v1_three_path_vlrerank `
  --limit 5 `
  --run-name product-multimodal-prod-v1-smoke
```

确认 smoke 的 JSON/Markdown 报告正常生成后，去掉 `--limit 5` 跑完整 50 条。云端 v1 指标应与本地 v1 报告接近；若有明显偏差，先检查云端 collection 的实体数、图片 embedding 失败日志、模型配置和图片 URL，不要直接切换生产运行时。

## 6. 成本与验证边界

正式导入会对每个有图商品调用一次文本 embedding 与一次图片 embedding；不会生成图文融合 embedding。脚本逐批写入并记录图片 embedding 失败数量；单张图片失败时写入零图片向量，但文本/BM25 路仍保留。

本脚本只创建/更新指定的三路 collection，不修改 `product_mm_collection`、`product_mm_v2` 或知识库 collection。
