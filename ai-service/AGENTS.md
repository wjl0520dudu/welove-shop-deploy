# AGENTS.md

This file applies to the Python `ai-service`. It extends the repository-level `AGENTS.md`.

## Responsibility

`ai-service` is an independent FastAPI application, usually on port `8000`, used by `chat-service`.

Main areas:

- Assistant run and stream APIs.
- LangGraph-based request analysis, routing, subtask execution, and response synthesis.
- Shopping agent tools and product-card memory.
- Knowledge/RAG retrieval through Milvus and reranking.
- Multimodal shopping retrieval with text, image, and product vectors.
- PostgreSQL checkpoint/store persistence with in-memory fallback.

## Code Map

- `main.py`: FastAPI app, middleware, lifespan initialization, and router registration.
- `api`: API routers for assistant and RAG endpoints.
- `assistant`: graph state, nodes, routing, orchestration, and runtime.
- `shopping`: shopping agent, product recommendation, comparison, detail answering, multimodal search.
- `knowledge`: knowledge-agent behavior.
- `rag`: parsing, indexing, retrieval, stats, and admin delete/search logic.
- `core`: configuration, logging, clients, and shared infrastructure.
- `tools`: external or internal tool wrappers.
- `prompts`: prompt templates.
- `tests`: Python tests.

## Rules

- Keep API payloads compatible with `services/chat-service`.
- Prefer modifying the graph/tool node that owns the behavior instead of adding broad conditionals in routers.
- Keep shopping, knowledge, chitchat, and unknown request paths separated.
- Image URLs should continue to force the multimodal shopping path unless the task changes routing semantics.
- Treat Milvus, DashScope, qwen rerank/VL, Bocha fallback, and Java API callbacks as configurable integrations.
- Do not hard-code local secrets or model keys. Use environment variables and `.env.example`.
- When changing product card data, inspect frontend chat rendering and Java chat persistence.

## Verification

Use the local environment available in `ai-service`. Typical checks:

```powershell
python -m pytest
python -m compileall .
```

If external services are unavailable, run import/compile checks and document which integration paths were not exercised.

