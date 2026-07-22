# AGENTS.md

This file applies to `services/product-service`. It extends `services/AGENTS.md`.

## Responsibility

`product-service` usually runs on port `8082` and owns product catalog data.

Main areas:

- Categories, products, SKUs, images, FAQ, and reviews.
- Hot/list/detail/search APIs for the user app.
- Internal/admin product management APIs.
- Recommendation exposure/click/order logs.
- Redis caching for detail, category, and hot-product data.

## Code Map

- `controller`: user-facing, internal, and admin-facing catalog endpoints.
- `service` and `service.impl`: catalog logic, search, recommendations, and cache behavior.
- `mapper`: MyBatis Plus persistence.
- `entity`: `product_svc` table mappings.
- `vo`: response view objects.
- `cache`: cache constants and helpers.

## Rules

- Keep product, SKU, image, FAQ, and review relationships consistent.
- Current search is database/search-service style logic with LIKE, synonym expansion, and scoring. Do not assume a dedicated search engine unless adding one intentionally.
- When changing product response shape, inspect user app product pages, chat product cards, admin product management, and AI-service product tools.
- Keep recommendation logs append-oriented unless the task requires aggregation changes.
- Add schema/seed changes in service-local Flyway migrations.

## Verification

```powershell
mvn -pl services/product-service -am test
```

