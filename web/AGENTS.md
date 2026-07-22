# AGENTS.md

This file applies to frontend applications under `web`. It extends the repository-level `AGENTS.md`.

## Applications

- `admin-web`: React + Vite admin console.
- `welove-shop`: uni-app/Vue user-facing shop.

Each app has its own local `AGENTS.md`; follow the app-specific file for implementation details.

## Shared Frontend Rules

- Call backend APIs through the gateway path prefixes.
- Keep HTTP logic in API/service modules rather than raw calls inside page components.
- Preserve token storage and `401` handling conventions for the app being changed.
- Keep UI changes consistent with the target app's existing design language.
- Verify mobile behavior for `welove-shop`; verify dense admin workflows for `admin-web`.
- Do not edit generated build outputs under `dist` or dependencies under `node_modules`.

## API Path Reminder

Gateway prefix stripping means paths often include both the gateway service prefix and the controller prefix:

- Product example: `/api/product/product/list`
- Chat example: `/api/chat/chat/stream/messages`
- Trade example: `/api/trade/cart/list`
- Admin example: `/api/admin/...`

