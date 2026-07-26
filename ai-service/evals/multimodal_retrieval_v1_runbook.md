# 多模态商品检索实验 v1：运行手册

本实验使用冻结的 50 条数据集，比较 v1～v5，并输出可横向对比的 JSON 与 Markdown 报告。实验 collection 固定为 `product_mm_eval_v1`，不会修改线上商品检索使用的 collection。

## 需要启动的环境

| 阶段 | PostgreSQL | Milvus / Zilliz | Redis | Nacos / Java 服务 / AI FastAPI |
|---|---|---|---|---|
| 建实验索引 | 必须 | 必须 | 不需要 | 不需要 |
| 跑检索评测 | 不需要 | 必须 | 不需要 | 不需要 |

还需要本机 `ai-service/.env` 中已有：`DASH_SCOPE_API_KEY`、文本/多模态 embedding 模型、VL rerank 模型、Milvus 连接信息、`IMAGE_BASE_URL`。商品图与 50 条查询图均须能由公网 HTTPS 访问。

## 第一次运行：建立独立实验索引

在 PowerShell 执行：

```powershell
cd ai-service
$env:MILVUS_PRODUCT_V2_COLLECTION = "product_mm_eval_v1"

# 只检查 PG、Milvus 和商品读取，不调用 embedding，不产生模型费用
python scripts/sync_products_to_milvus_v2.py --mode full --dry-run

# 100 个商品写入独立实验 collection；会调用 text embedding、图片 embedding、图文融合 embedding
python scripts/sync_products_to_milvus_v2.py --mode full --batch-size 10
```

## 跑 50 条正式评测

保持同一个 PowerShell 窗口（或再次设置 collection 环境变量）：

```powershell
python scripts/run_multimodal_retrieval_v1_experiment.py `
  --collection product_mm_eval_v1 `
  --run-name multimodal-retrieval-v1
```

输出文件：

- `evals/reports/multimodal-retrieval-v1.json`：逐 query 结果、商品 ID、人工等级、耗时，后续自动对比使用。
- `evals/reports/multimodal-retrieval-v1.md`：总体指标表，人工阅读使用。

先做小范围联调可运行：

```powershell
python scripts/run_multimodal_retrieval_v1_experiment.py --collection product_mm_eval_v1 --limit 2 --run-name multimodal-retrieval-v1-smoke
```

## 后续做第二轮实验

不覆盖第一轮报告，换 collection 与报告名即可，例如：

```powershell
$env:MILVUS_PRODUCT_V2_COLLECTION = "product_mm_eval_v2"
python scripts/sync_products_to_milvus_v2.py --mode full --batch-size 10
python scripts/run_multimodal_retrieval_v1_experiment.py --collection product_mm_eval_v2 --run-name multimodal-retrieval-v2
```

比较两份 JSON 时必须保持相同的 `dataset_sha256`、50 条 query、top_k 和模型配置；这样指标变化才能归因于检索方案/索引版本，而不是测试数据变化。
