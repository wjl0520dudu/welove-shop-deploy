# AGENTS.md

This file applies to infrastructure and local environment configuration under `infra`. It extends the repository-level `AGENTS.md`.

## Responsibility

`infra` contains local/shared configuration used to run the system, such as development application configuration.

## Rules

- Treat these files as environment configuration, not business logic.
- Keep defaults aligned with service-local `application.yml` files.
- Do not commit secrets, tokens, API keys, private endpoints, or machine-specific passwords.
- When changing ports, Nacos, Redis, PostgreSQL, Milvus, OSS, or AI-service URLs, inspect all services that reference the same setting.
- Prefer documenting required environment variables over hard-coding sensitive values.

## Verification

For config-only changes, verify by inspecting the affected services and running the smallest relevant startup/build check available.

