# AGENTS.md

This file applies to `services/chat-service`. It extends `services/AGENTS.md`.

## Responsibility

`chat-service` usually runs on port `8084` and bridges the user/admin apps with the Python AI service.

Main areas:

- Conversations and messages.
- SSE text and multimodal streaming.
- Chat image upload and storage.
- Knowledge documents, notices, QA logs, and agent run logs.
- Assistant responses, product cards, sources, stop/truncated status, and persistence.
- HTTP/WebClient/RestTemplate proxying to `ai-service`.

## Code Map

- `controller`: chat, stream, upload, knowledge, notice, QA, and admin/internal endpoints.
- `service` and `service.impl`: persistence, AI proxying, stream orchestration, and admin workflows.
- `mapper`: MyBatis Plus persistence.
- `entity`: `chat_svc` table mappings.
- `dto` and `vo`: request/response and stream payload models.
- `config`: AI service URL, web client, storage, security, and infrastructure config.

## Rules

- Treat SSE behavior as a contract with `web/welove-shop/src/pages/chat/chat.vue`.
- When changing AI request/response payloads, inspect `ai-service/api` and `ai-service/assistant`.
- Persist assistant answers, product cards, sources, and status transitions consistently.
- Preserve stop/truncated handling. The frontend expects resumable and final states to be explicit.
- Keep upload object keys compatible with configured storage and existing database columns.
- Add schema changes in service-local Flyway migrations.

## Verification

```powershell
mvn -pl services/chat-service -am test
```

