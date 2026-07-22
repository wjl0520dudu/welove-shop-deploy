# AGENTS.md

This file applies to Java business microservices under `services`. It extends the repository-level `AGENTS.md`.

## Services

- `user-service`: users, SMS-code login, token refresh, profile, addresses, favorites, browsing history.
- `product-service`: categories, products, SKUs, images, FAQ, reviews, search, hot products, recommendation logs.
- `trade-service`: carts, orders, order status, unpaid-order timeout handling.
- `chat-service`: conversations, messages, SSE streaming, uploads, knowledge docs, notices, QA logs, agent run logs, AI-service proxying.

## Shared Patterns

- Controllers return `Result<T>` or `PageResult<T>` from `common-core`.
- Use service classes for business logic and mapper classes for persistence.
- Use Feign clients for cross-service reads.
- Keep entities aligned with service-local Flyway migrations.
- Keep API paths compatible with gateway prefix stripping.
- Avoid direct database access across another service's schema.

## Database

Each service owns its own PostgreSQL schema:

- `user-service`: `user_svc`
- `product-service`: `product_svc`
- `trade-service`: `trade_svc`
- `chat-service`: `chat_svc`

Add schema changes in `src/main/resources/db/migration`.

## Verification

Run focused builds from the repository root:

```powershell
mvn -pl services/user-service -am test
mvn -pl services/product-service -am test
mvn -pl services/trade-service -am test
mvn -pl services/chat-service -am test
```

