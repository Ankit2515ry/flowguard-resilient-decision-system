# FlowGuard Frontend Plan

## Scope and architectural fit

This plan covers a separate React + TypeScript operator interface for the existing FastAPI
service. It does not change the submitted backend behavior or the location of
`docs/ASSIGNMENT_REPORT.md`. The checked-out branch for this work is
`feature/frontend-dashboard`; the original submission commit is `faa0d99`.

The existing architecture decision in `project_management/DECISIONS.md` says FastAPI and
Swagger are the MVP interface and that no React frontend is included. The requested frontend
is a new, explicitly scoped presentation layer. It must continue to treat FastAPI as the
authority for workflow rules, state transitions, retries, decisions, audit records, and
version activation. The modular monolith and immutable configuration contracts remain in
force.

## 1. Existing API endpoint inventory

Routes are registered by `app/main.py`. The current app exposes 11 paths:

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | None | Process health (`{"status":"ok"}`). |
| `POST` | `/api/v1/requests` | `Idempotency-Key` header | Validate and accept a request; does not execute it. |
| `GET` | `/api/v1/requests/{request_id}` | None | Read persisted status, stage, revision, timestamps, and decision when available. |
| `POST` | `/api/v1/requests/{request_id}/execute` | None | Explicitly trigger execution; repeat calls return current persisted state. |
| `GET` | `/api/v1/requests/{request_id}/audit` | None | Read persisted per-request audit events in sequence order. |
| `GET` | `/api/v1/requests/{request_id}/explanation` | None | Read persisted traces/results and pending/final explanation. |
| `GET` | `/api/v1/workflows` | None | List workflows with their active version and checksum. |
| `GET` | `/api/v1/workflows/{workflow_id}/versions` | None | List persisted versions and active flags. |
| `GET` | `/api/v1/reviews` | `X-Admin-Token` | List pending manual reviews. |
| `POST` | `/api/v1/reviews/{request_id}/resolve` | `X-Admin-Token` | Resolve pending review as approve/reject with reason. |
| `POST` | `/api/v1/admin/workflows/activate` | `X-Admin-Token` | Activate a persisted workflow version. |

There is no endpoint to list/search all requests, inspect the server's admin activation audit
log, or start/process retries. Retry execution is an out-of-band one-shot worker command.
Workflow input schemas are not exposed through an API; the UI cannot generically discover
form fields from the current backend.

## 2. Request and response data contracts

All JSON validation and HTTP errors are backend-owned. `app/main.py` wraps errors as
`{"error":{"code":"...","message":"...","details":...}}`; validation errors can
include `details` entries with `location`, `message`, and `type`. Common status codes include
`401` missing admin header, `403` incorrect admin token, `404` absent resource/workflow,
`409` conflicting idempotency/review state, `422` invalid body/input, `500` unexpected
failure, and `503` unconfigured admin authentication. UI error handling should parse this
shape and fall back to HTTP status text when the body is unavailable or malformed.

### Intake: `POST /api/v1/requests`

Request body (`RequestCreate`, extra properties forbidden at the top level):

```json
{
  "workflow_id": "loan_approval",
  "data": {
    "applicant": {
      "age": 24,
      "monthly_income": 60000,
      "credit_score": 750
    }
  }
}
```

The required `Idempotency-Key` header is 1-255 characters. Intake validates `data` against
the active version's structural schema, persists a pinned version, and returns
`request_id`, `status`, `workflow_id`, `config_version`, and relative `status_url`. A new
request responds `202`; a semantically identical replay responds `200` with
`Idempotency-Replayed: true`; the same scoped key with different content responds `409`.
The UI should generate and retain one key for a submission attempt so retrying the same
payload can safely reuse it, and should not claim that accepted intake has executed.

### Status and execution

`GET /api/v1/requests/{request_id}` and the execute response return a `RequestStatus`:

```json
{
  "request_id": "<uuid>", "status": "RECEIVED", "workflow_id": "loan_approval",
  "config_version": 2, "current_stage": "eligibility", "revision": 0,
  "created_at": "<date-time>", "updated_at": "<date-time>", "decision": null
}
```

`decision` is either null or `{outcome, explanation, created_at}`. Statuses observed in the
backend lifecycle include `RECEIVED`, `PROCESSING`, `RETRY_WAIT`, `MANUAL_REVIEW`,
`APPROVED`, `REJECTED`, and `FAILED`. Execution is a separate POST. The UI can offer an
explicit execute action while status is `RECEIVED`; subsequent state refreshes should use
GET. The frontend does not schedule retries or decide when retry jobs are due.

### Explanation and audit

Explanation returns `request_id`, `workflow_id`, `config_version`, `status`, nullable
`decision_outcome`, `pending`, `summary`, arrays `rule_traces`, `stage_results`,
`external_results`, and nullable `review_resolution`. These arrays contain backend-defined
objects; render their returned identifiers, values, results, and reason fields defensively,
without recomputing them. `pending: true` means no final decision is available.

Audit is an array of events with `sequence`, `event_type`, nullable `old_state`, `new_state`,
nullable `stage`, `created_at`, `config_version`, and arbitrary `details`. Events are
persisted history, ordered by sequence. A null stage is valid.

### Workflow discovery and administration

`GET /api/v1/workflows` returns an array of `{workflow_id, active_version, checksum}`.
`GET /api/v1/workflows/{workflow_id}/versions` returns an array of
`{workflow_id, version, checksum, is_active}`.

The review queue returns entries with `request_id`, `workflow_id`, `config_version`, status,
`current_stage`, and `created_at`. Resolution body is exactly
`{"action":"APPROVE"|"REJECT","reason":"..."}`; reason must be nonblank and at most
2000 characters. Response contains `request_id`, `status`, `decision_outcome`, and `replayed`.
Activation body is `{workflow_id, version}` with version >= 1; response is
`{workflow_id, active_version, changed}`. These operations use `X-Admin-Token`.

## 3. React screen plan

1. **Overview**: show live health and workflows/active versions from the API. Do not show
   invented totals, approval rates, latency, or retry metrics; no aggregate API supplies
   these values.
2. **New request**: choose a discovered workflow and enter its data. Initially support a
   narrowly scoped loan example form matching the currently inspected input schema, plus a
   raw JSON editor/fallback for other workflows. Show validation errors from the API. Label
   the screen as submission, and offer the separate execution action after acceptance.
3. **Request detail**: look up by request UUID (because list/search is absent), show live
   status and pinned version, and expose explicit execute only for `RECEIVED`. Include
   explanation and audit views.
4. **Manual review**: list pending review items, display request reference/version, collect
   action and reason, and submit with clear conflict/auth errors.
5. **Workflow versions**: inspect versions and active marker; offer an explicit activation
   control for admins and display backend response. Never edit workflow YAML or infer rules.
6. **Admin access**: session-only token entry for protected operations, with a clear
   connection/auth state and a sign-out control.

Shared UI should include loading, empty, backend-offline, malformed-response, and request
error states; accessible labels and keyboard focus; responsive navigation; and restrained
status colors. React Router should provide the screen URLs, including request detail by UUID.

## 4. Proposed folder structure

```text
frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  postcss.config.js
  tailwind.config.ts
  .env.example
  src/
    main.tsx
    App.tsx
    router.tsx
    index.css
    api/
      client.ts
      errors.ts
      types.ts
      requests.ts
      workflows.ts
      reviews.ts
    auth/
      AdminSession.tsx
      useAdminSession.ts
    components/
      AppShell.tsx
      Button.tsx
      ErrorNotice.tsx
      LoadingState.tsx
      StatusBadge.tsx
    features/
      overview/
      requests/
      reviews/
      workflows/
      admin/
```

Keep endpoint calls and wire types under `src/api`; view components should not construct
ad-hoc fetch behavior. Avoid adding a state-management dependency unless actual UI complexity
requires it.

## 5. API integration strategy

- Use native `fetch` from a small typed client, with a configurable base URL and centralized
  JSON/error parsing. Treat response bodies as untrusted at runtime despite TypeScript types.
- Use `VITE_API_BASE_URL` for deployed/non-proxy API configuration. In local development,
  configure Vite to proxy `/api` and `/health` to `http://127.0.0.1:8000`; use relative URLs
  so normal local work does not require backend CORS changes.
- Keep endpoint methods faithful to backend behavior. Intake POST must include a generated
  `Idempotency-Key`; execute remains an explicit POST. Never add client-side decision,
  transition, eligibility, retry, or audit logic.
- Refresh status/detail on demand and after user actions. If polling is used while active,
  bound it to a modest interval and stop on terminal/hidden screens; it only reads server
  state and does not drive workflow behavior.
- API-provided relative `status_url` should be resolved against the configured API base, not
  assumed to share the browser origin in deployed environments.
- Display backend error messages safely as text. Do not log request payloads/admin headers
  to analytics or console.

## 6. Authentication approach for demo administration

The backend uses one configured shared credential in `X-Admin-Token`, mapped to fixed actor
`demo-admin`; it is not user identity/RBAC. Do not include a credential in source, `.env`
commits, examples beyond an empty variable, or frontend build-time `VITE_*` settings (those
are public). Prompt the operator to enter the token at runtime. Keep it only in React memory
for the current tab session, send it only to protected review/activation endpoints, and clear
it on sign-out or reload. Do not use localStorage, sessionStorage, URL parameters, or cookies
as token storage. This means reload requires re-entry. Surface backend `401`, `403`, and `503`
responses distinctly without exposing the token. The demo token remains visible to the
operator who enters it and is not a production security boundary.

## 7. Implementation phases and acceptance criteria

1. **Scaffold and connectivity**: create Vite React/TypeScript app with Tailwind, Router,
   Lucide, API base configuration and local proxy. Acceptance: app starts; route shell loads;
   API client handles JSON and the documented error envelope; no CORS backend changes.
2. **Read-only overview and discovery**: health, workflows, versions and request detail by
   ID with explanation/audit. Acceptance: values are API-backed; empty/loading/error states
   work; no fabricated aggregates or client-side decisions.
3. **Request intake and execution**: workflow selection, schema-aware initial form, generated
   idempotency key, accepted response, explicit execute, status refresh. Acceptance: payload
   conforms to inspected schema; duplicate-safe retries reuse the key; execution requires
   user action; backend owns all outcomes.
4. **Admin review and activation**: in-memory token entry, queue, resolution and version
   activation. Acceptance: token is sent only as `X-Admin-Token`, never persisted; forms
   match Pydantic contracts; API auth/conflict errors are visible.
5. **Polish and verification**: responsive/accessibility pass, document run/config steps, run
   frontend checks and preserve Python suite. Acceptance: documented frontend checks pass;
   existing Python tests remain passing; `project_management/FRONTEND_PROGRESS.md` records
   actual commands and outcomes. No implementation phase begins until explicitly requested.

## 8. Backend capabilities missing for the frontend

- Request collection/search/pagination/filter endpoint. Detail lookup therefore needs a
  manually supplied UUID (including after a submission) or locally retained non-sensitive
  recent IDs; server history cannot be browsed.
- Workflow input schema discovery endpoint. The frontend must initially use a known example
  form or raw JSON and can only rely on backend validation errors.
- Aggregate metrics/dashboard endpoint. Do not display totals, success rates, or retry
  metrics as if authoritative.
- Retry queue/worker control/status endpoint. Retry processing stays an operator-run worker
  command; the UI can only display a request's current `RETRY_WAIT` state.
- Admin activation audit history endpoint. The UI can show current active versions and
  activation responses, but cannot show historical administrator changes.
- Production identity, per-user roles, credential rotation, and token revocation. Existing
  shared demo token is the only protected-endpoint mechanism.

These are capability gaps, not reasons to change backend behavior in the frontend phase.
Any API expansion requires separate backend scope and explicit direction.

## 9. Risks and integration assumptions

- The submitted backend remains authoritative; the frontend is a separate, optional client.
- The current README loan example aligns with loan v2's structural schema. Other workflow
  forms must be confirmed by inspecting their actual schema before implementation.
- Backend request/audit/explanation reads are unauthenticated and request-ID scoped. Avoid
  presenting UUIDs as access control or exposing them in public URLs beyond the intended demo.
- Browser CORS is avoided locally through Vite proxy. A separately hosted production UI will
  need same-origin deployment/proxy or a narrowly scoped deployment CORS decision, not a
  broad backend CORS change.
- In-memory admin token storage is intentionally ephemeral and per-tab. It is suitable only
  for the shared-credential demo model.
- `status_url` is relative, so callers must resolve it using API base URL semantics.
- No server-provided form metadata, aggregation, request list, or worker state exists; avoid
  assumptions that these can be inferred from returned values.
- Date/time values are backend timestamps. Render them as dates without relying on local
  formatting to imply workflow ordering; audit `sequence` is the ordering authority.
