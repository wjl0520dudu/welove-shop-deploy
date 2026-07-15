# AGENTS.md

This file defines repository-level guidance for `welove-shop-agt`. More specific `AGENTS.md` files in child directories extend this file; when instructions conflict, the deeper file wins for work under that directory.

## Project Map

This repository contains a shopping application with Java microservices, a Python AI service, and two frontend applications.

- `gateway`: Spring Cloud Gateway entrypoint on port `8080`.
- `common`: shared Java libraries for result envelopes, exceptions, security, database config, web handling, and storage.
- `services/user-service`: user login, profile, address, favorite, and browsing history APIs.
- `services/product-service`: category, product, SKU, review, FAQ, search, and recommendation-log APIs.
- `services/trade-service`: cart and order APIs.
- `services/chat-service`: chat conversations, messages, SSE, upload, knowledge docs, notices, QA logs, and agent logs.
- `admin-bff`: admin login and admin-facing aggregation/forwarding APIs.
- `ai-service`: FastAPI AI service using LangGraph, RAG, Milvus, DashScope, and multimodal shopping retrieval.
- `web/admin-web`: React/Vite admin console.
- `web/welove-shop`: uni-app/Vue user-facing shop.
- `db`: database scripts and auxiliary SQL. Current Java services primarily use service-local Flyway migrations.
- `infra`: local infrastructure configuration such as shared dev config.

## System Architecture

Main user traffic flows through the gateway:

- `/api/user/**` routes to `user-service`.
- `/api/product/**` routes to `product-service`.
- `/api/trade/**` routes to `trade-service`.
- `/api/chat/**` routes to `chat-service`.
- `/api/admin/**` routes to `admin-bff`.

Java services use Nacos at `127.0.0.1:8848` by default, PostgreSQL schemas per service, and Redis where configured. The Python AI service is called by `chat-service`, usually through `AI_SERVICE_URL=http://127.0.0.1:8000/api`.

## Backend Conventions

- Keep service ownership boundaries intact. Put business logic in the service that owns the data.
- Use `common-core` response and exception types instead of inventing per-service envelopes.
- Preserve the existing layered structure: `controller`, `service`, `service.impl`, `mapper`, `entity`, `dto`, `vo`, `feign`, and `config`.
- Prefer MyBatis Plus and existing mapper/service patterns.
- Use Flyway scripts under each Java service for schema changes.
- Keep cross-service calls behind Feign clients.
- Do not bypass `UserContext` or security interceptors for authenticated user APIs.
- Avoid unrelated refactors across services when implementing a feature.

## Frontend Conventions

- Keep admin and user app code separate. Shared behavior should only be extracted when both apps truly need it.
- Frontend APIs call the gateway paths, for example `/api/product/product/list` and `/api/chat/chat/stream/messages`.
- Respect each app's existing stack: React/Vite for `admin-web`, uni-app/Vue for `welove-shop`.
- Keep API calls in existing API/service modules rather than scattering raw HTTP calls in pages.

## AI Service Conventions

- Treat `ai-service` as an independent Python app. Do not mix Java service concerns into it.
- Keep LangGraph routing, shopping tools, knowledge/RAG tools, and multimodal retrieval responsibilities separated.
- When changing chat behavior, inspect both `services/chat-service` and `ai-service`.
- When changing product recommendation behavior, inspect `services/product-service`, `ai-service/shopping`, and the frontend chat/product card rendering.

## Data Notes

Primary PostgreSQL schemas are:

- `user_svc`
- `product_svc`
- `trade_svc`
- `chat_svc`
- `admin_svc`

The root `db` directory may contain older or auxiliary scripts. Prefer service-local Flyway migrations for active Java service schema changes unless the task specifically targets shared database setup.

## Verification

Use the fastest relevant verification for the touched area:

- Java: `mvn -pl <module> -am test` or `mvn -pl <module> -am package -DskipTests` when tests are not practical.
- Admin frontend: run commands from `web/admin-web`, typically `npm run build`.
- User frontend: run commands from `web/welove-shop`, typically `npm run build:h5` if available.
- AI service: run focused Python tests or import checks from `ai-service`.

If verification cannot be run because local services, databases, Nacos, Redis, Milvus, or environment variables are unavailable, state that explicitly.

