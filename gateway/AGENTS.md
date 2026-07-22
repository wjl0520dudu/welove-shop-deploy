# AGENTS.md

This file applies to the Spring Cloud Gateway module. It extends the repository-level `AGENTS.md`.

## Responsibility

`gateway` is the external Java entrypoint, usually on port `8080`. It routes frontend and admin requests to internal services and applies gateway-level filters.

Current route families:

- `/api/user/**` to `user-service`
- `/api/product/**` to `product-service`
- `/api/trade/**` to `trade-service`
- `/api/chat/**` to `chat-service`
- `/api/admin/**` to `admin-bff`

Routes use prefix stripping, so frontend paths often contain the service segment twice, for example `/api/product/product/list`.

## Rules

- Keep gateway routing consistent with service controller prefixes.
- Do not place business logic in the gateway.
- Be careful changing CORS, auth, path rewriting, and timeout settings because both frontends depend on them.
- If adding a new backend module, add route config here and confirm service registration name in Nacos.
- When debugging 404s, inspect the frontend path, gateway StripPrefix behavior, and target controller path together.

## Verification

For route-only changes, inspect `application.yml` and run:

```powershell
mvn -pl gateway -am package -DskipTests
```

