# ScoreMe Submission Checklist

## Deliverables

- [x] Runnable Python 3.11+ FastAPI workflow platform with Swagger UI.
- [x] README with PowerShell setup, quick start, API examples, retries and troubleshooting.
- [x] Architecture, HLD, LLD and trade-off documents.
- [x] Versioned YAML workflows/rules for loan v1/v2 and vendor v1.
- [x] REST API for intake, status, execution, audit, explanation, reviews and activation.
- [x] Unit, integration and failure tests for rules, persistence, duplicates, retries,
  concurrency, rollback, review and configuration activation.
- [x] Persisted audit history and decision explanation examples.
- [x] Scaling considerations and trade-off defence.
- [x] Requirement-to-code/test/limitation matrix in
  [`REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md).
- [x] Final report: [`ASSIGNMENT_REPORT.md`](ASSIGNMENT_REPORT.md).

## Verified commands and outcomes

Run from the repository root with the existing `.venv`:

| Command | Verified outcome |
|---|---|
| `.venv\Scripts\python.exe -m pip install -e ".[dev]"` | Passed; FlowGuard editable install and dev dependencies available. |
| `.venv\Scripts\python.exe -m pytest -q` | **91 passed, 1 upstream deprecation warning.** |
| `.venv\Scripts\python.exe -m compileall -q app` | Passed. |
| `git diff --check` | Passed; only line-ending normalization notices. |
| In-process isolated app smoke | `/health`, `/docs`, and `/openapi.json` verified with an in-memory SQLite database. |

Final evidence is recorded in [`../project_management/TEST_RESULTS.md`](../project_management/TEST_RESULTS.md).

## GitHub publishing checklist (manual; not performed)

- [ ] Confirm the desired GitHub account, repository name and visibility.
- [ ] Inspect `git status`, review the final diff, and confirm no `.env`, database, `.venv`,
  WAL/SHM, cache or credential files are staged.
- [ ] Commit the submission documentation if desired.
- [ ] Create the GitHub repository in the intended account.
- [ ] Add the repository URL as `origin`, for example:
  `git remote add origin https://github.com/<account>/<repository>.git`.
- [ ] Push the intended branch, for example `git push -u origin main`.
- [ ] Open the repository URL in a browser and verify that source, report and README are
  accessible; copy the verified URL for the email.
- [ ] Do not state that publishing occurred until the push and URL are verified.

Current workspace has no configured Git remote, and no repository has been created or pushed.

## Email submission (manual; not sent)

- Recipient: `it@scoreme.in`
- Subject: `assignment_mnnit_scoreme_rollno` (lowercase; replace `rollno` with the actual
  roll number).
- Include the verified GitHub repository link and link or attach
  [`ASSIGNMENT_REPORT.md`](ASSIGNMENT_REPORT.md).
- Deadline note from the assignment instructions: submit by the stated **7:00 PM** finish;
  confirm the applicable date/time with ScoreMe.

No email has been sent. The actual roll number and verified repository URL are not available
in this workspace.

## Known limitations

- External calls are at-least-once across a crash after provider success and before local
  commit; exactly-once external effects are not claimed.
- SQLite serializes writes; one retry worker is supported, with no lease heartbeat.
- Admin access uses a shared demo token and fixed actor, not production identity/RBAC.
- Audit and explanation reads are request-ID scoped and unauthenticated in this MVP.
- Schema initialization uses additive SQLite startup logic; Alembic migrations are deferred.
- The test run reports one upstream Starlette TestClient/httpx deprecation warning.
- A local ignored `flowguard.db` exists with one APPROVED request and three config snapshots.
  Ownership is uncertain; Phase 7 verification used in-memory/temporary databases and no
  operation targeted this file. Do not delete it without approval.

## Submission blockers and next action

The code and report are prepared locally. Publishing requires the owner to choose/create a
GitHub destination; the email subject also requires the actual roll number. Neither GitHub
publishing nor email delivery was performed by this agent.
