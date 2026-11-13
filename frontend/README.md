# FlowGuard frontend

FlowGuard's React + TypeScript operator console for the existing FastAPI backend. It supports
workflow discovery, loan/vendor request intake, explicit execution, request status/audit/
explanation reads, manual review, and version activation. The Python backend remains the
source of truth for workflow decisions, state transitions, retries, and audit records.

## Requirements

- Python 3.11+ and the repository `.venv` dependencies
- Node.js 20.19+ or 22.12+ and npm (Vite 8 requirement)
- Windows PowerShell examples below use `npm.cmd` because the local PowerShell script policy
  may prevent running `npm.ps1`

## Run backend and frontend together

Use two PowerShell terminals from the repository.

### Terminal 1: backend

From the repository root, install the backend if needed, select a dedicated local demo
database, set a demo admin token at runtime, and start FastAPI:

```powershell
if (!(Test-Path .venv)) { py -3.11 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

$env:FLOWGUARD_DATABASE_URL = "sqlite:///./flowguard-frontend-demo.db"
$env:FLOWGUARD_ADMIN_TOKEN = Read-Host -Prompt "Enter a local demo admin token"
$env:FLOWGUARD_SIMULATOR_SCENARIO = "SUCCESS"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The dedicated `flowguard-frontend-demo.db` is ignored by Git and keeps this demo separate
from `flowguard.db`. Keep the backend terminal running. The token is supplied at runtime;
do not put it in frontend configuration or commit it.

### Terminal 2: frontend

From the repository root:

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run dev
```

Open the local Vite URL printed by the dev server. Vite proxies `/api` and `/health` to
`http://127.0.0.1:8000` by default, so local development does not require backend CORS
changes. To change the proxy target, set `FLOWGUARD_API_PROXY_TARGET` before starting Vite.
For an API hosted at another browser-accessible origin, set `VITE_API_BASE_URL` before
starting Vite; this value is public configuration and must not contain credentials. The API
docs link follows this configured origin, or points to the default local backend when unset.

The admin token is entered in the UI at runtime, held only in React memory, and sent only in
`X-Admin-Token` headers for protected review and activation requests. Reloading the page
clears it and requires re-entry.

## Frontend checks

From `frontend/`:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

## Verified journeys

The following backend API contracts are covered by the existing isolated FastAPI integration
tests (temporary or in-memory SQLite databases):

- Health and available workflow/version discovery.
- Valid loan intake (`202`), duplicate replay (`200`), and changed-payload idempotency
  conflict (`409`).
- Explicit loan execution and approval, request lookup, ordered persisted audit, and stored
  decision explanation.
- A v2 loan request with credit score 710 enters manual review; authenticated resolution
  updates the decision and audit. Wrong/missing admin credentials and conflicting review
  actions return the expected errors.
- Workflow activation updates the version used for new requests; loan v1 approves the 710
  example while v2 routes it to review, and existing requests retain their pinned version.
- Finalized requests, replay behavior, retry states, and persisted external attempt history.

Latest verification recorded in `project_management/FRONTEND_PROGRESS.md`. Backend API tests
verify the service contracts used by the UI; they do not simulate browser clicks or establish
a live browser session between Vite and Uvicorn.

## Manual browser checks still needed

Run these against the two local servers above:

1. Visit Dashboard and verify the backend indicator changes from checking to connected and
   the displayed workflow IDs/active versions match `GET /api/v1/workflows`. Stop the API and
   confirm the indicator and page error/empty states remain usable.
2. At a desktop width and a narrow mobile width, visit every sidebar route. Use keyboard Tab,
   Enter, and Escape/close controls to check navigation, labels, focus visibility, and mobile
   drawer behavior.
3. Submit loan values age 24, monthly income 60000, credit score 750. Confirm the UI shows
   request ID, selected workflow, pinned version, and `202`; explicitly execute and confirm
   status, explanation, audit, and external attempt data are the API response values. Use
   Copy request ID and paste it into Request Details.
4. Submit the same logical payload again with a simulated uncertain network response only
   if a safe local proxy/network interruption can be arranged. Confirm the explicit retry
   sends the same payload/key; confirm a normal new submission gets a new UUID key. Do not
   claim this browser retry flow is verified by the backend unit tests alone.
5. Enter a valid loan UUID manually, inspect status/audit/explanation, and try a malformed
   UUID and an unknown valid UUID to check validation and 404 feedback.
6. Submit a v2 loan with credit score 710, execute it, enter the runtime admin token, load
   Manual Reviews, and resolve it with a nonblank reason. Confirm the review queue refreshes
   and the request detail reflects the backend's resolution.
7. Enter an incorrect admin token and verify the 403 message. To exercise stale review
   conflict handling, load the same review in two tabs, resolve it in one, then resolve the
   stale item in the other and confirm the 409 message/queue refresh path.
8. Activate loan v1, then submit a new 710-score request and verify the backend response.
   Activate loan v2 and repeat. Check that the version list refreshes and the UI explains
   that previously accepted requests keep their pinned version.
9. Use browser devtools to confirm the admin token is absent from localStorage, sessionStorage,
   cookies, URLs, and built frontend assets; it should appear only in memory and protected
   request headers.

## Known limitations

- The backend has no request-list/search endpoint, so requests must be opened with a UUID.
- Input schemas are not served by an API. The UI has explicit loan and vendor forms based on
  the current checked-in schema files; other workflows cannot be submitted through these
  forms.
- No aggregate metrics, retry-worker controls, or admin activation audit history endpoint
  exists. The dashboard does not invent request counts or charts; due retry work still uses
  the backend's separate worker command.
- Admin access is a shared demo token, not production identity or role-based authorization.
- For a separately hosted frontend, use same-origin proxying or a deliberate narrowly scoped
  CORS setup. The local Vite proxy is for development only.
- Browser interaction checks above remain manual; no browser automation dependency is
  included in this project phase.
