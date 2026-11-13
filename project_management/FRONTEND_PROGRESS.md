# Frontend Progress

## Current state

Frontend Phases 1-5 are implemented on `feature/frontend-dashboard`. The React + TypeScript
dashboard shell, request intake/execution/inspection, persisted audit/explanation views, and
admin review/version activation screens are present. Phase 5 verification and local setup
documentation are complete. Backend code and the assignment report were not changed.

## Analysis completed

- Verified branch `feature/frontend-dashboard`; original submitted commit is `faa0d99`.
- Read `AGENTS.md`, `README.md`, `project_management/HANDOFF.md`, `MASTER_PLAN.md`,
  `TASKS.md`, `PROGRESS.md`, and `DECISIONS.md` (the project-management records are under
  `project_management/`; root-level `TASKS.md`, `PROGRESS.md`, and `DECISIONS.md` do not
  exist).
- Inspected FastAPI route registration, handlers, Pydantic request/response models, admin
  token dependency behavior, service response construction, the loan v2 input schema, and
  architecture contracts.
- At the initial analysis baseline, no `frontend/` directory existed. The API has 11 paths
  including `/health` and lacks request search/list, schema discovery, aggregate metrics,
  retry-worker controls, and activation audit history.
- Recorded API contracts, screens, proposed structure, API/auth strategy, phases, gaps,
  assumptions, and risks in `docs/FRONTEND_PLAN.md`.

## Frontend Phase 1 completed

- Replaced the JavaScript Vite starter with a TypeScript React application using React Router,
  Lucide React, Tailwind CSS 4 and `@tailwindcss/vite`.
- Added a responsive sidebar/header shell and Dashboard, Submit Request, Request Details,
  Manual Reviews, Workflow Configuration, and Not Found routes. Empty states explain actual
  backend limits; no request data, charts, or metrics are fabricated.
- Added a centralized native Fetch client with configurable `VITE_API_BASE_URL`, request
  headers/body support, abort signals, and structured backend error parsing. The only live
  UI call is the existing `GET /health` endpoint.
- Configured the Vite `/api` and `/health` proxy to `http://127.0.0.1:8000` by default, with
  `FLOWGUARD_API_PROXY_TARGET` override. No backend CORS or runtime behavior changed.
- Added strict TypeScript configuration, `npm run typecheck`, and Windows PowerShell setup
  commands in `frontend/README.md`. PowerShell's `npm` script shim was blocked by the local
  execution policy, so verification used `npm.cmd` as documented.
- Verification: `npm.cmd run typecheck` passed; `npm.cmd run lint` passed; `npm.cmd run
  build` passed (Vite 8.3.8). npm install reported 0 vulnerabilities. Build output is ignored.
- Git status inspection confirmed `frontend/node_modules/` and `frontend/dist/` are ignored;
  neither is tracked. `frontend/package-lock.json` was updated with TypeScript.

## Frontend Phase 2 completed

- Added typed API contracts and client functions for `GET /api/v1/workflows`, request intake,
  request status, and explicit execution. Intake captures the actual HTTP code to distinguish
  new `202` acceptance from `200` idempotent replay.
- The dashboard now displays workflows and active versions returned by the backend. It does
  not show synthetic request totals or other invented metrics.
- Added loan and vendor forms matching the actual input schema YAML: applicant age, monthly
  income, and credit score; vendor registration status, tax clearance, sanctions-clear flag,
  and annual turnover. The frontend does not evaluate eligibility or constrain business
  values; server validation remains authoritative.
- New logical submissions use `crypto.randomUUID()` as `Idempotency-Key`. If the response is
  uncertain (network failure or server 5xx), an explicit retry action resends the exact saved
  payload with the same key. No automatic POST retry is performed. Known 409/422 errors ask
  for correction/new submission and do not reuse that attempt's key.
- Successful submission displays request ID, selected workflow, backend-pinned version,
  status, and the accepted/replay HTTP result. Execution is a separate user action using the
  execute endpoint; then the client reads current persisted state through the GET status
  endpoint. Status can also be refreshed explicitly.
- Request Details now accepts a UUID lookup, reports malformed/missing/backend errors, and
  shows the persisted request status and explicit execute/refresh controls.
- Verification: `npm.cmd run typecheck` passed; `npm.cmd run lint` passed without warnings;
  `npm.cmd run build` passed with Vite 8.3.8. No backend tests were run because no backend
  files changed. `dist/` and `node_modules/` remain ignored.

## Frontend Phase 3 completed

- Added typed read APIs for `GET /api/v1/requests/{id}/audit` and
  `GET /api/v1/requests/{id}/explanation`, matching the actual Pydantic response envelope
  and backend-persisted fields. Explanation trace/external attempt structures were checked
  against `app/engine/rules.py`, `app/services/workflow_executor.py`, and API integration
  tests.
- Request Details now loads status, audit, and explanation for a valid manual UUID lookup.
  Audit events are sorted by their persisted `sequence` before rendering a chronological
  timeline; returned state changes, event details, timestamps, versions, and optional stage
  are displayed without creating events.
- Added persisted rule trace cards with pass/fail, actual/expected values, operator, backend
  reason, failure action, and config version. Added external verification attempt history
  using returned attempt number, result, retryability, category, message, operation, and key.
- Current stage comes from the request status response. Pending/terminal indicators use the
  explanation's backend `pending`, `decision_outcome`, and `status` fields. Execution stays
  a user-triggered backend operation; the browser does not evaluate rules.
- Empty explanations and audit histories, pre-execution traces/attempts, and per-endpoint
  errors have explicit states. After explicit execution or status refresh, the page reloads
  persisted audit/explanation data.
- Verification: `npm.cmd run build`, `npm.cmd run lint`, and `npm.cmd run typecheck` passed.
  Relevant backend API contract tests: `.venv\\Scripts\\python.exe -m pytest
  tests/integration/test_phase5_api.py -q` passed **13 tests** with one upstream
  Starlette/httpx deprecation warning. No backend files changed.

## Frontend Phase 4 completed

- Added shared admin session context held only in React memory. The runtime password input is
  cleared after connection; credentials are not stored in local/session storage, cookies,
  URLs, or committed configuration. Forgetting the token also clears review queue data.
- Added authenticated review queue reads and resolution using only existing endpoints and
  `X-Admin-Token`. Approval/rejection require a trimmed reason (max 2000 characters) and
  explicit browser confirmation. Successful resolution reloads the queue and displays the
  backend result.
- Added workflow version listing using existing workflow/version APIs and explicit confirmed
  activation using the existing admin activation endpoint. The page refreshes current active
  version data after success and explains that accepted requests retain their pinned version.
- Added clear 403 forbidden, 409 conflict, missing/unconfigured auth, loading, empty, success,
  and backend error states. No new backend API was created and no credentials were hardcoded.
- Verification: `npm.cmd run build`, `npm.cmd run lint` (no warnings), and
  `npm.cmd run typecheck` passed. Relevant backend API tests
  `.venv\\Scripts\\python.exe -m pytest tests/integration/test_phase5_api.py -q` passed
  **13 tests**, with one upstream Starlette/httpx deprecation warning. No backend files
  changed; generated `dist/` and `node_modules/` remain ignored.

## Frontend Phase 5 completed

- Inspected the actual frontend routes and API client calls, FastAPI handlers/schemas,
  workflow/version contracts, proxy/base-origin configuration, auth header handling, and Git
  ignore/environment configuration. No unsupported API route was found. The existing
  `docs/ASSIGNMENT_REPORT.md` path and content were unchanged.
- Fixed two confirmed UX integration issues: the API docs link now follows
  `VITE_API_BASE_URL` when configured, and request IDs have a keyboard-accessible Copy button
  with success/error feedback.
- Rewrote `frontend/README.md` with two-terminal backend/frontend PowerShell commands, a
  dedicated ignored demo database, token-at-runtime guidance, verified backend journeys,
  known limitations, and an exact manual browser checklist.
- Frontend verification: `npm.cmd run typecheck` passed; `npm.cmd run lint` passed without
  warnings; `npm.cmd run build` passed with Vite 8.3.8.
- Static Vite preview route smoke returned HTTP 200 and the SPA root document for `/`,
  `/submit`, `/requests`, `/reviews`, `/workflows`, and an unknown route (React's Not Found
  rendering still requires the manual browser pass).
- Backend regression: `.venv\\Scripts\\python.exe -m pytest -q` passed **91 tests** with
  one upstream Starlette/httpx deprecation warning. Focused API journey set passed **12 tests**
  with the same warning. Test fixtures use temporary or in-memory SQLite; no database URL
  environment variable was configured for the run.
- Verified API contracts covered by those tests: health; request intake `202`, duplicate
  `200` replay and mismatch `409`; loan execution/approval/status; ordered audit and stored
  explanation; v2 manual review and authenticated approve/reject; wrong-token `403`, review
  `409`; activation and active-version discovery; v1/v2 distinct outcomes and preserved
  request pins.
- Browser click-through was not automated in this environment. Exact manual browser checks
  are listed in `frontend/README.md`; do not interpret the backend API tests as a browser
  end-to-end run.
- Repository safety: current branch is `feature/frontend-dashboard`; `main` remains at
  original submitted commit `faa0d99`. `node_modules/`, `dist/`, `.env`, and SQLite database
  patterns are ignored. No staging, commit, push, or merge was performed.
- No local `.env` files were present; the process had no `FLOWGUARD_*` or `VITE_*` values set.
  `.env.example` was inspected with values redacted; its admin token entry is empty.
- `git diff --check` passed. Generated frontend `dist/` and `node_modules/` are not tracked.

## Verification and next step

- Phase 5 is complete. No further frontend phase was started. The branch is prepared for
  owner review and commit; backend behavior remains unchanged.
