# AGENTS.md

This file applies to `admin-bff`. It extends the repository-level `AGENTS.md`.

## Responsibility

`admin-bff` usually runs on port `8090` and serves the React admin console through gateway path `/api/admin/**`.

Main areas:

- Admin login and admin token handling.
- Dashboard aggregation.
- Admin user, product, order, conversation, knowledge, QA, notice, agent, and recommendation APIs.
- Feign forwarding/aggregation to business services.

## Code Map

- `controller`: admin-facing API endpoints.
- `service` and `service.impl`: admin auth, aggregation, and forwarding logic.
- `mapper` and `entity`: `admin_svc` persistence.
- `dto`: request/response and downstream DTOs.
- `feign`: clients for user, product, trade, and chat services.
- `interceptor`: admin authentication.
- `config`: security, Feign, and app configuration.

## Rules

- Keep admin API response shapes compatible with `web/admin-web`.
- Do not duplicate business mutations here if the owning service already exposes an internal/admin endpoint.
- Use BFF logic for aggregation and presentation shaping, not as a second source of business truth.
- Keep admin auth separate from user auth unless a task explicitly unifies them.
- Add schema changes in `src/main/resources/db/migration`.

## Verification

```powershell
mvn -pl admin-bff -am test
```

