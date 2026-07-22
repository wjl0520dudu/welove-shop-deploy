# AGENTS.md

This file applies to `services/user-service`. It extends `services/AGENTS.md`.

## Responsibility

`user-service` usually runs on port `8081` and owns user-facing identity/profile data.

Main areas:

- SMS-code login, token refresh, and current-user profile.
- Address CRUD and default-address behavior.
- Favorite products and browsing history.
- Product enrichment through Feign calls to `product-service`.

## Code Map

- `controller`: external and internal user APIs.
- `service` and `service.impl`: business logic.
- `mapper`: MyBatis Plus persistence.
- `entity`: `user_svc` table mappings.
- `dto` and `vo`: request and response models.
- `feign`: product-service clients and DTOs.
- `config`: Redis, security, and service configuration.

## Rules

- Use `UserContext` for authenticated user identity.
- Keep token/JWT behavior aligned with `common-security`.
- Do not denormalize product details into user tables unless the feature explicitly needs snapshots.
- For favorites and history, fetch current product details through the existing product-service client.
- Add table changes through `src/main/resources/db/migration`.

## Verification

```powershell
mvn -pl services/user-service -am test
```

