# FlowGuard frontend

React + TypeScript operator console for the FlowGuard FastAPI backend. Phase 1 provides the
responsive navigation shell, placeholder workspace states, live backend health status, and
the typed native Fetch API client. Request intake/execution, request lookup, workflow
discovery, and authenticated review operations are not enabled yet.

## Requirements

- Node.js 20.19+ or 22.12+ (Vite 8 requirement)
- npm
- FlowGuard API at `http://127.0.0.1:8000` for the health indicator

## Start locally

In one terminal, start the backend from the repository root using the project README setup.
Then run the frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Vite forwards `/api` and `/health` to `http://127.0.0.1:8000` by default. To use a different
proxy target, set `FLOWGUARD_API_PROXY_TARGET` before `npm run dev`. For an API hosted at a
different browser-accessible origin, set `VITE_API_BASE_URL` in your local shell before
starting Vite, for example:

```powershell
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

`VITE_API_BASE_URL` is public frontend configuration and must never contain credentials.
Leave it unset for the local proxy. No admin token is stored or requested in this phase.

## Checks

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

The API client is in `src/api/client.ts`; backend health uses the existing `GET /health`
endpoint. Errors are parsed from the backend's `{ "error": { "code", "message", "details" } }`
envelope when available.
