# semantic_v1 Runbook

## Purpose

`semantic_v1` is experiment B in the chunking comparison:

- product knowledge stays identical to v2.1: marketing description, one FAQ Q&A, and each group of three reviews are separate semantic units;
- general knowledge is split at complete Markdown topics (`##`), with an oversized topic split only at complete `###` subtopics;
- it is a single-layer index. It does not enable parent-child retrieval.

The target collection is intentionally new: `knowledge_semantic_v1`.

## 1. Configure `.env`

In `ai-service/.env`, set the following experiment values before ingestion and evaluation:

```env
MILVUS_COLLECTION=knowledge_semantic_v1
RAG_PARENT_CHILD_ENABLED=false
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

`CHUNK_SIZE` and `CHUNK_OVERLAP` remain fixed to preserve retrieval settings across experiments. `semantic_v1` does not use them to cut general knowledge; it uses Markdown topic boundaries.

## 2. Inspect the new chunk layout

```powershell
cd ai-service

python scripts/ingest_semantic_v1.py `
  --collection knowledge_semantic_v1 `
  --dry-run
```

Check that product rows use `marketing`, `faq`, and `review` units, while general rows use `general_topic` units. This command makes no Milvus or embedding request.

## 3. Import the local experiment collection

```powershell
python scripts/ingest_semantic_v1.py `
  --collection knowledge_semantic_v1 `
  --source all `
  --replace
```

The collection is created automatically when it does not exist. `--replace` deletes each incoming `doc_id` before insertion, making later full reruns idempotent. It does not affect `my_rag_collection` or `knowledge_recursive_v1`.

## 4. Verify mixed retrieval before RAGAS

```powershell
python scripts/verify_mixed_knowledge.py
```

Confirm that general queries retrieve `general_knowledge` topic chunks and product queries retrieve `product_knowledge` semantic chunks. This is a retrieval smoke check; it does call Milvus, embedding, and rerank.

## 5. Run the 32-case RAGAS experiment

```powershell
python -m evals.run_agent_eval `
  --direct `
  --scenario knowledge `
  --ragas `
  --dataset evals/datasets/agent_golden_cases.jsonl `
  --output evals/reports/agent-semantic-v1.json `
  --markdown-output evals/reports/agent-semantic-v1.md
```

`--direct` does not require FastAPI to be running. Milvus, the embedding endpoint, rerank endpoint, and LLM/RAGAS endpoint must be available.

## 6. Compare the three single-layer candidates

Use the same dataset and evaluation code to compare:

| Strategy | Collection |
|---|---|
| Fixed v2.1 baseline | `my_rag_collection` |
| Recursive v1 + general | `knowledge_recursive_v1` |
| Semantic v1 | `knowledge_semantic_v1` |

Prioritize paired RAGAS results on shared successful case IDs, then check Recall@5, MRR@5, NDCG@5, and RAGAS failure counts. Do not use latency alone to select a chunking strategy.

## 7. Restore the v2.1 baseline

After the experiment, restore the runtime collection in `.env`:

```env
MILVUS_COLLECTION=my_rag_collection
RAG_PARENT_CHILD_ENABLED=false
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```
