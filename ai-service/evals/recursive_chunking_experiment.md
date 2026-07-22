# Recursive Chunking Experiment (recursive_v1)

## Experiment Identity

- **Version**: recursive_v1
- **Date**: 2026-07-22
- **Objective**: Evaluate whether `RecursiveCharacterTextSplitter` (chunk_size=500, overlap=50) improves over fixed `CharacterTextSplitter` (chunk_size=500, overlap=50) for knowledge RAG retrieval and answer quality.
- **Baseline versions**: v2.1 (fixed chunking, `my_rag_collection`), v2.3 (parent-child chunking, `knowledge_parent_child_v1`)

---

## Frozen Case List

Cases selected for this experiment satisfy **all** of:
1. `scenario == "knowledge"`
2. `ragas_reference` is present in `agent_golden_cases.jsonl`
3. Evaluated in both v2.1 and v2.3 RAGAS reports

**Frozen case IDs** (18 total):
```
rag-001, rag-002, rag-003, rag-004, rag-005, rag-006, rag-007, rag-008,
rag-009, rag-010, rag-011, rag-012, rag-014, rag-015, rag-016, rag-017,
rag-018, rag-024, rag-029
```

Note: rag-013, rag-019, rag-020, rag-021, rag-022, rag-023, rag-025, rag-026, rag-027, rag-028 have `ragas_reference` in the dataset but either v2.1 or v2.3 evaluation may not have returned valid RAGAS scores (e.g., context_precision/context_recall skipped). Only the 18 above have full four-metric (faithfulness, answer_relevancy, context_precision, context_recall) coverage in both reports.

---

## Constraints

| Constraint | Value |
|---|---|
| Chunking method | `RecursiveCharacterTextSplitter` |
| chunk_size | 500 |
| chunk_overlap | 50 |
| Milvus collection | `knowledge_recursive_v1` (独立 collection，不污染默认 collection) |
| RAG_PARENT_CHILD_ENABLED | false |
| Retrieval | hybrid (dense + BM25), initial_top_k=20, use_rerank=true, top_k=5 |
| Embedding model | text-embedding-v4 (DashScope) |
| Rerank model | qwen3-rerank |
| LLM (answer generation) | qwen-plus |
| RAGAS LLM | qwen-plus |
| RAGAS embedding | text-embedding-v4 |
| Dataset fingerprint | `d7c852af8570e81f` (agent_golden_cases.jsonl) |
| Prompt fingerprint | `f49c054eb71b5d7e` (shared with v2.1/v2.3) |

---

## Execution Steps

### Step 1 — Create Milvus Collection
Use the existing `create_vector_store()` infrastructure but target `knowledge_recursive_v1`.
The collection schema must match the default `knowledge` collection schema (dense_vector 1024dim + sparse_vector BM25).

### Step 2 — Ingest Knowledge Documents
Use `scripts/ingest_recursive_v1.py` to:
1. Read the same product JSON files as `ingest_knowledge_v2.py` (from `backend/db/data/ecommerce_agent_dataset/`)
2. For each product's `rag_knowledge` (marketing_description, official_faq, user_reviews), call `build_recursive_chunks_from_text()` with chunk_size=500, chunk_overlap=50
3. Upsert into `knowledge_recursive_v1`

Also ingest the static markdown knowledge docs (护肤知识-*.md content embedded in `ingest_knowledge.py`'s DOCUMENTS list) using `build_recursive_chunks_from_text()`.

### Step 3 — Smoke Test
Verify chunking quality manually on 5 frozen cases:
- rag-001 (烟酰胺作用) — ingredient term
- rag-007 (视黄醇+维C) — compatibility question with strong semantic boundary
- rag-008 (果酸+视黄醇) — compatibility with mixed Chinese/English punctuation
- rag-013 (精华步骤) — short question, general knowledge
- rag-015 (防晒频率) — usage question

For each, verify:
- Top20 raw candidates from Milvus
- Reranked Top5
- Retrieved context content
- That the doc_id and chunk_index reference the correct source

### Step 4 — Run RAGAS Evaluation
```bash
cd ai-service
export MILVUS_COLLECTION=knowledge_recursive_v1
export RAG_PARENT_CHILD_ENABLED=false
python -m evals.run_agent_eval --direct --deepeval --ragas \
    --case-ids-file evals/datasets/recursive_v1_frozen_cases.json
```

### Step 5 — Generate Reports
Outputs:
- `evals/reports/agent-recursive-v1.json`
- `evals/reports/agent-recursive-v1.md`

---

## Success Criteria

Primary metrics (RAGAS):
- **Answer Relevancy**: ≥ v2.3 score (0.8+ is strong)
- **Context Precision**: ≥ v2.3 score
- **Context Recall**: ≥ v2.3 score
- **Faithfulness**: ≥ v2.3 score

Secondary:
- Contract pass rate on frozen cases ≥ v2.3 knowledge pass rate
- Latency P95 comparable to v2.1/v2.3

---

## Fallback Handling

Any case with `fallback_used=true` in the retrieval output must be **flagged separately** and **excluded from Milvus chunking主结论**. These cases indicate the recursive chunker failed to retrieve relevant chunks and the system fell back to web search (Bocha), which is outside the scope of the chunking experiment.

---

## Version Comparison Table (to be filled after experiment)

| Metric | v2.1 (fixed) | v2.3 (parent-child) | recursive_v1 | Notes |
|---|---|---|---|---|
| Answer Relevancy (mean) | TBD | TBD | TBD | |
| Context Precision (mean) | TBD | TBD | TBD | |
| Context Recall (mean) | TBD | TBD | TBD | |
| Faithfulness (mean) | TBD | TBD | TBD | |
| Contract Pass Rate | TBD | TBD | TBD | |
| Latency P50 (ms) | 14130 | 7696 | TBD | |
| Latency P95 (ms) | 18323 | 17810 | TBD | |
| Total Chunks | TBD | TBD | TBD | |
| Avg Chunk Length | TBD | TBD | TBD | |
| Cases Evaluated | 32 | 32 | TBD | |

---

## Representative Case Analysis

After experiment, select:
- **1 improvement case**: where recursive-v1 scores higher than both v2.1 and v2.3
- **1 degradation case**: where recursive-v1 scores lower than both
- **1 mixed/inconclusive case**: where retrieval is correct but faithfulness is low, or fallback interfered

For each case, document: case ID, question, top-5 retrieved doc_ids, RAGAS scores, answer excerpt, and analysis.

---

## Conclusion Template

```
recursive_v1 vs v2.3:
- [BETTER / WORSE / EQUIVALENT] on Answer Relevancy
- [BETTER / WORSE / EQUIVALENT] on Context Precision
- [BETTER / WORSE / EQUIVALENT] on Context Recall
- [BETTER / WORSE / EQUIVALENT] on Faithfulness

recursive_v1 vs v2.1:
- [BETTER / WORSE / EQUIVALENT] on overall RAGAS mean

Recommendation:
- [PROCEED to small-parent-child comparison / DO NOT PROCEED]
- If DO NOT PROCEED, primary bottleneck is: [chunking / recall / rerank / context fill / generation]
```
