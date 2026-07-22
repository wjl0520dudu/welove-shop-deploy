# AGENTS.md

This file applies to `web/welove-shop`. It extends `web/AGENTS.md`.

## Stack

- uni-app + Vue 3.
- Vite-based H5 development.
- Pinia-like stores under `src/store`.
- API modules under `src/api`.

## App Map

- `src/pages.json`: page and tab configuration.
- `src/pages/chat/chat.vue`: AI shopping chat, text stream, image upload, multimodal stream, product cards, SKU sheet, and cart actions.
- `src/pages/product/*`: product list/detail flows.
- `src/pages/cart/*`: cart flows.
- `src/pages/order/*`: order confirmation/list/detail flows.
- `src/pages/address/*`: address management.
- `src/pages/favorite/*` and `src/pages/history/*`: favorite and browsing history.
- `src/store/user.js`: token/profile restore, login, logout.
- `src/store/chat.js`: conversation/message cache, stream records, new-message markers.
- `src/store/cart.js`: cart item/count and tab badge state.
- `src/utils/sse.js`: H5 POST SSE implementation using `fetch` and `ReadableStream`.

## Rules

- Treat `pages/chat/chat.vue` as a sensitive integration point with `chat-service` and `ai-service`.
- Preserve background stream continuation, stop/truncated handling, and message persistence behavior unless the task specifically changes it.
- Keep product card and SKU data shapes compatible with chat-service persistence and product-service responses.
- Use existing API modules under `src/api` for backend calls.
- Keep UI mobile-first and touch-friendly.
- Verify tab bar badge behavior when changing cart or login state.
- Do not edit generated `dist` files or bundled `uni_modules` code unless the task explicitly targets them.

## Verification

From `web/welove-shop`, use the available scripts in `package.json`. Prefer:

```powershell
npm run build:h5
```

If that script is unavailable, run the closest H5 build/check command listed in `package.json`.

