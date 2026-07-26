# 多模态商品检索子链路实验结论（v1）

## 1. 实验范围

本实验评估的是 ShoppingAgent 内部的**多模态商品检索子链路**，目标是选出“图片 + 用户文本”场景下最合适的商品召回与排序结构。

不评估完整 Agent 的意图路由、工具调用、推荐话术或商品卡片渲染；这些应另用 Agent Golden Test 做端到端评测。

## 2. 实验固定条件

| 项目 | 值 |
|---|---|
| 商品向量库 | 本地 Milvus `product_mm_v2` |
| 商品语料 | 当前 100 条商品 |
| 查询集 | `evals/datasets/multimodal_retrieval_v1.jsonl`，50 条 |
| 数据集指纹 | `e9faa0cc1f0d193f83fbda99c76be31788bcc423497ebb1107b50e72c36978b2` |
| 返回数量 | Top10 |
| 相关性标注 | 人工冻结 `relevance_grades`：2=强相关，1=弱相关，未标注=0 |
| 评测指标 | NDCG@5、NDCG@10、Recall@5、Recall@10、MRR、Hit@1、平均耗时 |
| LLM-as-Judge | 未使用；主指标完全由冻结商品 ID 标注计算 |

所有方案共享相同语料、数据集、TopK、模型配置和筛选条件。

## 3. 对比方案

| 方案 | 召回向量字段 | 排序方式 |
|---|---|---|
| v1 | `text_dense_vector` + `text_sparse_vector`（BM25）+ `image_vector` | RRF → `qwen3-vl-rerank` |
| v2 | v1 三路 + `multimodal_vector` | RRF → `qwen3-vl-rerank` |
| v3 | v2 四路 | 固定权重排序，无 rerank |
| v4 | 仅 `multimodal_vector` | 单路向量排序，无 rerank |
| v5 | 仅 `multimodal_vector` | Top20 → `qwen3-vl-rerank` → Top10 |

字段来源：

```text
text_dense_vector  = text-embedding-v4（商品结构化文本）
text_sparse_vector = Milvus BM25 Function（商品结构化文本）
image_vector       = qwen3-vl-embedding（商品图片）
multimodal_vector  = qwen3-vl-embedding enable_fusion（商品文本 + 商品图片）
```

`qwen3-vl-rerank` 是候选精排模型，不是向量字段。

## 4. 实验结果

运行报告：

- `evals/reports/multimodal-retrieval-v1.json`
- `evals/reports/multimodal-retrieval-v1.md`

| 方案 | NDCG@5 | NDCG@10 | Recall@5 | Recall@10 | MRR | Hit@1 | 平均耗时(s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **v1 三路 + VL rerank** | **0.914** | **0.920** | **0.965** | **0.973** | **0.895** | **0.820** | 2.89 |
| v2 四路 + VL rerank | 0.894 | 0.900 | 0.945 | 0.953 | 0.875 | 0.800 | 4.09 |
| v3 四路 + Weighted | 0.833 | 0.861 | 0.888 | 0.937 | 0.838 | 0.760 | 3.27 |
| v4 单路图文融合 | 0.781 | 0.827 | 0.817 | 0.927 | 0.805 | 0.740 | **1.04** |
| v5 单路图文融合 + VL rerank | 0.886 | 0.892 | 0.935 | 0.943 | 0.875 | 0.800 | 2.72 |

## 5. 结论与原因

### 5.1 最终选择：v1 三路召回 + VL rerank

v1 在全部核心效果指标上最高：NDCG@5 为 0.914、Recall@10 为 0.973、MRR 为 0.895、Hit@1 为 0.820。它是后续云端正式商品向量库的目标检索结构。

```text
用户查询文本 → text dense 检索 + BM25 检索
用户查询图片 → image vector 检索
三路结果 → RRF 融合
Top20 候选 → qwen3-vl-rerank
输出 Top10 商品
```

### 5.2 图文融合第四路不全局启用

v2 比 v1 的 NDCG@5 低 0.020，Recall@10 低 0.020，且平均慢 1.20 秒。

主要回退样本为 `new-030`：图像内容是防晒，用户文本实际要“搭配一款适合油皮的洁面”。v1 将商品 11（洁面）排第一；v2 加入图文融合召回后，候选被图像主题牵引，前排变成防晒、卸妆等商品。说明图文融合向量对跨类搭配意图可能产生干扰。

### 5.3 VL rerank 必须保留

v4 到 v5 的 NDCG@5 从 0.781 提升到 0.886，证明 VL rerank 对图文候选排序有明显增益。即使生产采用 v1，也必须保留该精排步骤。

## 6. 云端商品向量库导入决策

后续导入 Zilliz Cloud 时，建立独立生产 collection，建议命名：

```text
product_multimodal_prod_v1
```

生产索引只需要 v1 实际使用的字段：

| 字段 | 是否导入 | 原因 |
|---|---:|---|
| `product_id` 与商品元数据 | 是 | 返回商品卡片、筛选和追踪 |
| `text` | 是 | BM25 Function 输入 |
| `text_dense_vector` | 是 | 文本稠密召回 |
| `text_sparse_vector` | 是 | Milvus BM25 稀疏召回输出 |
| `image_vector` | 是 | 图片相似召回 |
| `multimodal_vector` | 否 | v1 不使用；不再为生产导入支付图文融合 embedding 成本 |

因此生产导入流程应是：

```text
PG 商品数据 + 已验证的 OSS 商品图
→ text-embedding-v4 生成 text_dense_vector
→ Milvus BM25 Function 生成 text_sparse_vector
→ qwen3-vl-embedding 生成 image_vector
→ 写入 product_multimodal_prod_v1
```

运行时固定使用三路 RRF + `qwen3-vl-rerank`，不启用 `multimodal_vector` 第四路。

## 7. 后续事项

1. 新增专用“三路生产索引”写入脚本与 collection schema；不要直接复用当前会写入 `multimodal_vector` 的 v2 全量同步脚本，避免无效的模型调用成本。
2. 在 Zilliz Cloud 以新 collection 完成一次全量导入。
3. 用同一份 50 条冻结数据集进行云端 smoke（至少 5 条）与完整回归（50 条），确认云端与本地结果没有异常偏差。
4. 再将 ShoppingAgent 多模态运行时 collection 配置切换到云端生产 collection。
