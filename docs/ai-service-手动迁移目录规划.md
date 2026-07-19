# ai-service 手动迁移目录规划

## 迁移原则

本方案只移动文件，不修改文件内容、不改文件名、不复制文件、不保留双份实现。

以 Git 原始基线为准，`main.py` 必须保留在 `ai-service` 根目录，保证：

```powershell
cd ai-service
uvicorn main:app
```

## 一、根目录

```text
ai-service/
├── .env.example
├── AGENTS.md
├── PR_SUMMARY.md
├── main.py
├── requirements.txt
├── requirements-eval.txt
├── app/
├── evals/
├── scripts/
└── tests/
```

## 二、API 层

```text
app/api/
├── __init__.py
├── assistant_routes.py
├── health_routes.py
├── logging_config.py
├── middleware.py
├── rag_routes.py
├── response_adapter.py
└── schemas.py
```

```text
api/__init__.py          → app/api/__init__.py
api/assistant_routes.py  → app/api/assistant_routes.py
api/health_routes.py    → app/api/health_routes.py
api/middleware.py       → app/api/middleware.py
api/rag_routes.py       → app/api/rag_routes.py
api/response_adapter.py → app/api/response_adapter.py
api/schemas.py          → app/api/schemas.py
core/logging_config.py  → app/api/logging_config.py
```

`logging_config.py` 当前依赖 `api.middleware`，第一阶段放在 API 层可以避免基础设施层反向依赖 API 层。

## 三、Assistant 应用层

```text
app/application/
├── __init__.py
└── assistant/
    ├── __init__.py
    ├── context_resolver.py
    ├── graph.py
    ├── nodes.py
    ├── orchestration.py
    ├── reference_tools.py
    ├── router.py
    ├── router_tools.py
    ├── schemas.py
    └── state.py
```

```text
agents/__init__.py             → app/application/__init__.py
assistant/__init__.py          → app/application/assistant/__init__.py
assistant/context_resolver.py  → app/application/assistant/context_resolver.py
assistant/graph.py             → app/application/assistant/graph.py
assistant/nodes.py             → app/application/assistant/nodes.py
assistant/orchestration.py     → app/application/assistant/orchestration.py
assistant/router.py            → app/application/assistant/router.py
agents/schemas.py              → app/application/assistant/schemas.py
agents/state.py                → app/application/assistant/state.py
tools/reference_tools.py       → app/application/assistant/reference_tools.py
tools/router_tools.py          → app/application/assistant/router_tools.py
```

暂时保留原文件名 `schemas.py`、`orchestration.py`，不要在第一阶段改名。

## 四、Shopping 领域层

```text
app/domain/shopping/
├── agent.py
├── cards.py
├── category_resolver.py
├── context.py
├── dispatcher.py
├── high_level_tools.py
├── models.py
├── multimodal_search.py
├── personalization.py
├── preferences.py
├── product_repository.py
├── ranking.py
├── relevance_judge.py
├── retrieval.py
├── schemas.py
├── capabilities/
│   ├── __init__.py
│   ├── compare.py
│   ├── detail.py
│   ├── recommend.py
│   └── user_context.py
└── tools/
    ├── shopping_tools.py
    └── user_tools.py
```

```text
shopping/agent.py                      → app/domain/shopping/agent.py
shopping/cards.py                      → app/domain/shopping/cards.py
shopping/category_resolver.py          → app/domain/shopping/category_resolver.py
shopping/context.py                    → app/domain/shopping/context.py
shopping/dispatcher.py                 → app/domain/shopping/dispatcher.py
shopping/high_level_tools.py           → app/domain/shopping/high_level_tools.py
shopping/models.py                     → app/domain/shopping/models.py
shopping/multimodal_search.py          → app/domain/shopping/multimodal_search.py
shopping/personalization.py            → app/domain/shopping/personalization.py
shopping/product_repository.py         → app/domain/shopping/product_repository.py
shopping/ranking.py                    → app/domain/shopping/ranking.py
shopping/relevance_judge.py            → app/domain/shopping/relevance_judge.py
shopping/retrieval.py                  → app/domain/shopping/retrieval.py
shopping/schemas.py                    → app/domain/shopping/schemas.py
agents/preferences.py                  → app/domain/shopping/preferences.py
shopping/capabilities/__init__.py     → app/domain/shopping/capabilities/__init__.py
shopping/capabilities/compare.py      → app/domain/shopping/capabilities/compare.py
shopping/capabilities/detail.py       → app/domain/shopping/capabilities/detail.py
shopping/capabilities/recommend.py    → app/domain/shopping/capabilities/recommend.py
shopping/capabilities/user_context.py → app/domain/shopping/capabilities/user_context.py
tools/shopping_tools.py               → app/domain/shopping/tools/shopping_tools.py
tools/user_tools.py                   → app/domain/shopping/tools/user_tools.py
```

## 五、Knowledge 领域层

```text
app/domain/knowledge/
├── __init__.py
├── agent.py
├── document_pipeline.py
├── models.py
├── query_planner.py
└── rag_tools.py
```

```text
knowledge/__init__.py      → app/domain/knowledge/__init__.py
knowledge/agent.py         → app/domain/knowledge/agent.py
rag/document_pipeline.py  → app/domain/knowledge/document_pipeline.py
rag/models.py              → app/domain/knowledge/models.py
rag/query_planner.py       → app/domain/knowledge/query_planner.py
tools/rag_tools.py         → app/domain/knowledge/rag_tools.py
```

## 六、基础设施层

### 1. 公共基础设施

```text
app/infrastructure/
├── __init__.py
├── config.py
└── errors.py
```

```text
core/__init__.py → app/infrastructure/__init__.py
core/config.py   → app/infrastructure/config.py
core/errors.py   → app/infrastructure/errors.py
```

### 2. 外部客户端

```text
app/infrastructure/clients/
├── java_api_client.py
└── mcp_client.py
```

```text
core/java_api_client.py → app/infrastructure/clients/java_api_client.py
knowledge/mcp_client.py → app/infrastructure/clients/mcp_client.py
```

### 3. LLM 相关

```text
app/infrastructure/llm/
├── llm.py
└── middleware.py
```

```text
core/llm.py           → app/infrastructure/llm/llm.py
agents/middleware.py  → app/infrastructure/llm/middleware.py
```

### 4. 持久化与运行时

```text
app/infrastructure/persistence/
├── database.py
├── memory.py
├── orm_models.py
└── runtime.py
```

```text
core/database.py        → app/infrastructure/persistence/database.py
agents/memory.py        → app/infrastructure/persistence/memory.py
agents/runtime.py       → app/infrastructure/persistence/runtime.py
shopping/orm_models.py  → app/infrastructure/persistence/orm_models.py
```

### 5. 检索基础设施

```text
app/infrastructure/retrieval/
├── __init__.py
├── embeddings.py
├── multimodal_embeddings.py
├── parent_child.py
├── reranker.py
└── retriever.py
```

```text
rag/__init__.py               → app/infrastructure/retrieval/__init__.py
rag/embeddings.py             → app/infrastructure/retrieval/embeddings.py
rag/multimodal_embeddings.py → app/infrastructure/retrieval/multimodal_embeddings.py
rag/parent_child.py           → app/infrastructure/retrieval/parent_child.py
rag/reranker.py               → app/infrastructure/retrieval/reranker.py
rag/retriever.py              → app/infrastructure/retrieval/retriever.py
```

### 6. Knowledge 向量库

```text
app/infrastructure/vectorstores/knowledge/
└── vector_store.py
```

```text
rag/vector_store.py → app/infrastructure/vectorstores/knowledge/vector_store.py
```

### 7. Product 向量库

```text
app/infrastructure/vectorstores/product/
├── vector_store.py
└── vector_store_v2.py
```

```text
shopping/vector_store.py    → app/infrastructure/vectorstores/product/vector_store.py
shopping/vector_store_v2.py → app/infrastructure/vectorstores/product/vector_store_v2.py
```

### 8. Pgvector

```text
app/infrastructure/vectorstores/pgvector/
├── __init__.py
├── engine.py
├── init.py
├── orm.py
└── pgvector_store.py
```

```text
pg_search/__init__.py        → app/infrastructure/vectorstores/pgvector/__init__.py
pg_search/engine.py          → app/infrastructure/vectorstores/pgvector/engine.py
pg_search/init.py            → app/infrastructure/vectorstores/pgvector/init.py
pg_search/orm.py             → app/infrastructure/vectorstores/pgvector/orm.py
pg_search/pgvector_store.py  → app/infrastructure/vectorstores/pgvector/pgvector_store.py
```

## 七、Prompt 文件

```text
app/prompts/
├── __init__.py
├── chitchat.py
├── knowledge_qa.py
├── prompts.py
├── shopping.py
└── title.py
```

```text
prompts/__init__.py   → app/prompts/__init__.py
prompts/chitchat.py   → app/prompts/chitchat.py
prompts/knowledge_qa.py → app/prompts/knowledge_qa.py
prompts/shopping.py   → app/prompts/shopping.py
prompts/title.py      → app/prompts/title.py
agents/prompts.py     → app/prompts/prompts.py
```

暂时不要拆分 `agents/prompts.py` 的内容，拆分 Prompt 属于代码内容变更。

## 八、历史模块

### Cart

```text
app/legacy/cart/
├── __init__.py
├── cart_agent.py
├── cart_tools.py
├── java_client.py
├── models.py
└── response_parser.py
```

```text
cart/__init__.py          → app/legacy/cart/__init__.py
cart/cart_agent.py        → app/legacy/cart/cart_agent.py
cart/java_client.py       → app/legacy/cart/java_client.py
cart/models.py            → app/legacy/cart/models.py
tools/cart_tools.py       → app/legacy/cart/cart_tools.py
agents/response_parser.py → app/legacy/cart/response_parser.py
```

### Chains

```text
app/legacy/chains/
├── __init__.py
├── knowledge_qa_chain.py
├── postprocess.py
├── rag_qa_chain.py
└── title_chain.py
```

```text
chains/__init__.py            → app/legacy/chains/__init__.py
chains/knowledge_qa_chain.py → app/legacy/chains/knowledge_qa_chain.py
chains/postprocess.py         → app/legacy/chains/postprocess.py
chains/rag_qa_chain.py        → app/legacy/chains/rag_qa_chain.py
chains/title_chain.py         → app/legacy/chains/title_chain.py
```

## 九、evals 目录保持原位

```text
evals/
├── __init__.py
├── agent_contract.py
├── agent_judges.py
├── agent_metrics.py
├── preference_metrics.py
├── retrieval_metrics.py
├── router_metrics.py
├── run_agent_eval.py
├── run_preference_eval.py
├── run_router_eval.py
└── datasets/
    ├── agent_golden_cases.jsonl
    ├── preference_cases.jsonl
    ├── router_cases.jsonl
    └── _v2_draft/
        ├── agent_golden_cases.v1.backup.jsonl
        ├── agent_golden_cases.v2.jsonl
        ├── build_v2.py
        ├── build_v2_router_pref.py
        ├── expand_multimodal.py
        ├── merge_retry.py
        ├── preference_cases.v1.backup.jsonl
        ├── preference_cases.v2.jsonl
        ├── router_cases.v1.backup.jsonl
        └── router_cases.v2.jsonl
```

## 十、scripts 目录保持原位

```text
scripts/
├── build_product_embeddings.py
├── cleanup_orphan_vectors.py
├── delete_doc_by_id.py
├── drop_milvus_collection.py
├── drop_product_mm_collection.py
├── eval_multimodal_retrieval.py
├── gen_mock_multimodal_queries.py
├── ingest_general_knowledge.py
├── ingest_knowledge.py
├── ingest_knowledge_v2.py
├── ingest_products_to_milvus.py
├── rebuild_knowledge_doc_from_milvus.py
├── reindex_knowledge_parent_child.py
├── sync_mysql_to_pg.py
├── sync_products_pg_to_milvus.py
├── sync_products_to_milvus_v2.py
├── test_bocha_fallback.py
├── test_llm_rules.py
├── test_orchestrator_planner.py
├── verify_full_stack_e2e.py
├── verify_mixed_knowledge.py
├── verify_pgvector.py
├── verify_product_search_modes.py
├── verify_rerank_effect.py
├── verify_retrieval_full.py
├── verify_retrieval_modes.py
├── verify_shopping_e2e.py
└── verify_shopping_focus_and_compare.py
```

## 十一、tests 目录保持原位

```text
tests/
├── __init__.py
├── _manual_e2e_router_reference.py
├── check_collections_size.py
├── check_pg_db_size.py
├── conftest.py
├── rag_qa_chain.ipynb
├── test_agent_evaluation.py
├── test_api_contract.py
├── test_assistant_graph.py
├── test_assistant_stream_filtering.py
├── test_cart_agent.py
├── test_cart_java_client.py
├── test_check_router.ipynb
├── test_context_resolver.py
├── test_dashscope.py
├── test_document_pipeline.py
├── test_embedding.ipynb
├── test_embedding.py
├── test_knowledge_entity_extraction.py
├── test_knowledge_qa_chain.py
├── test_multimodal_retrieval_v2.py
├── test_pending_shopping_need.py
├── test_personalization.py
├── test_postprocess.py
├── test_product_category_resolver.py
├── test_product_repository.py
├── test_product_vector_store.py
├── test_recommend_capability.py
├── test_reference_tools.py
├── test_relevance_judge.py
├── test_reranker.py
├── test_retiver.ipynb
├── test_retriever.py
├── test_retriever_modes.py
├── test_router.ipynb
├── test_router_reliability.py
├── test_router_tools.py
├── test_shopping_capabilities.py
├── test_shopping_high_level_tools.py
├── test_shopping_ranking_and_cards.py
├── test_shopping_retrieval.py
├── test_shopping_tools.py
├── test_sync_products.py
├── test_title_chain.py
├── test_vector_store.py
└── fixtures/
    ├── eval_judge_cache.json
    ├── eval_report.md
    └── mock_multimodal_queries.jsonl
```

## 十二、本地运行文件

以下文件不属于源码迁移范围，继续留在 `ai-service` 根目录：

```text
ai-service/.env
ai-service/ai-stdout.log
ai-service/ai-stderr.log
ai-service/.pytest_cache/
ai-service/.pytest_temp/
ai-service/__pycache__/
```

## 十三、推荐迁移顺序

使用 PyCharm 的 `Refactor -> Move`，不要直接用资源管理器拖动。

1. 移动 `app/api`。
2. 移动 `app/application/assistant`。
3. 移动 `app/infrastructure`。
4. 移动 `app/domain/knowledge`。
5. 移动 `app/domain/shopping`。
6. 移动 `app/legacy`。
7. 移动 `app/prompts`。
8. `scripts`、`evals`、`tests` 保持原位，仅让 PyCharm 更新 import。

每完成一个阶段执行：

```powershell
python -m compileall -q .
python -m pytest -q tests/test_api_contract.py tests/test_context_resolver.py
git diff --check
```

最重要的约束：

- `main.py` 不移动。
- 不改文件名。
- 不复制文件。
- 不保留旧实现和新实现两份代码。
- 每次只迁移一个目录组，确认导入和测试通过后再继续。
