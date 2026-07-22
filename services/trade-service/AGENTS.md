# AGENTS.md

This file applies to `services/trade-service`. It extends `services/AGENTS.md`.

## Responsibility

`trade-service` usually runs on port `8083` and owns cart/order behavior.

Main areas:

- Cart item list, add, update, delete, and count.
- Order creation, list, detail, cancel, payment simulation, shipping, and completion.
- Product/SKU validation through `product-service` Feign clients.
- Address lookup through `user-service` Feign clients.
- Scheduled cancellation of unpaid timeout orders.

## Code Map

- `controller`: cart and order APIs.
- `service` and `service.impl`: cart/order business logic.
- `mapper`: MyBatis Plus persistence.
- `entity`: `trade_svc` table mappings.
- `dto` and `vo`: request and response models.
- `feign`: product and user service clients.
- `task`: scheduled order maintenance.

## Rules

- Preserve order status semantics unless doing a deliberate migration:
  - `0`: unpaid
  - `1`: paid or pending delivery
  - `2`: shipped
  - `3`: completed
  - `4`: cancelled
- Validate product/SKU state before creating orders.
- Keep price and product snapshots on orders stable after order creation.
- Do not read product or user schemas directly; use Feign clients.
- Add schema changes in service-local Flyway migrations.

## Verification

```powershell
mvn -pl services/trade-service -am test
```

