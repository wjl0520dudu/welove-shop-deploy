# AGENTS.md

This file applies to `web/admin-web`. It extends `web/AGENTS.md`.

## Stack

- React + Vite.
- Axios API client with base URL `/api/admin`.
- Admin token and profile are stored as `adminToken` and `adminInfo`.

## App Map

- `src/main.*`: app bootstrap.
- `src/router` or route config files: page routing.
- `src/pages`: admin business pages such as login, dashboard, users, products, orders, conversations, knowledge, and QA logs.
- `src/api` or `src/services`: backend calls.
- `src/components`: reusable admin UI components.
- `src/utils`: shared helpers.

Some pages may exist while routes are commented out, including notices, inspection, agent runs, and recommendations. Confirm route registration before assuming a page is live.

## Rules

- Keep admin API response assumptions aligned with `admin-bff`.
- Use the configured Axios client. Do not scatter raw `fetch` calls for backend APIs.
- Keep admin workflows compact, scannable, and operations-focused.
- Include loading, empty, and error states for list/detail workflows when adding new pages.
- Be careful with destructive operations; use confirmation UI.
- Preserve auth redirect behavior when changing login or interceptors.

## Verification

From `web/admin-web`:

```powershell
npm run build
```

Run lint/test scripts too if they exist and are relevant.

