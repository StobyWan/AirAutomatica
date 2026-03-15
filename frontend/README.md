# AirAutomatica Frontend

Vue 3 SPA for the AirAutomatica dashboard.

## Setup

```bash
npm install
```

## Development

```bash
npm run dev
```

Runs Vite dev server on port 5173. Proxies API and Socket.io to FastAPI on 8000.

## Build

```bash
npm run build
```

For production when served at `/dashboard`:

```bash
VITE_BASE_PATH=/dashboard npm run build
```

## Production

When `frontend/dist/index.html` exists (or `USE_SPA_DASHBOARD=true`), FastAPI serves the SPA for `/dashboard` and `/dashboard/sessions/:id`. Legacy HTML templates remain available when the SPA is not built.
