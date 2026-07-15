# AGENTS.md

This file applies to the root `db` directory. It extends the repository-level `AGENTS.md`.

## Responsibility

This directory contains database setup, legacy, auxiliary, or cross-service SQL scripts. The active Java service migrations are usually under each service:

- `services/user-service/src/main/resources/db/migration`
- `services/product-service/src/main/resources/db/migration`
- `services/trade-service/src/main/resources/db/migration`
- `services/chat-service/src/main/resources/db/migration`
- `admin-bff/src/main/resources/db/migration`

## Rules

- Prefer service-local Flyway migrations for active schema changes.
- Use this root directory for shared setup, manual maintenance scripts, or explicitly requested global database artifacts.
- Label scripts clearly if they are PostgreSQL, MySQL, seed data, migration helpers, or one-off maintenance.
- Do not silently change legacy scripts to match new schemas unless the task asks for that cleanup.
- Keep schema ownership clear: user, product, trade, chat, and admin data should remain in their own schemas.

