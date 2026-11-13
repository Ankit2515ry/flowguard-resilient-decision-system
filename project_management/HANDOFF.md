# Handoff

## Verified local submission state

Phases 1-7 local preparation are complete. The final report is
`docs/ASSIGNMENT_REPORT.md`; the submission checklist is `docs/SUBMISSION_CHECKLIST.md`.
The final suite passed **91 tests** with one upstream Starlette TestClient/httpx deprecation
warning. Editable install, compileall, whitespace check and an in-memory API/Swagger/request
smoke are recorded in `TEST_RESULTS.md`.

The source tree is on branch `main`, latest commit at the start of Phase 7 was `2633a26`, and
no Git remote is configured. Phase 7 changes are local and uncommitted. No GitHub repository
was created/pushed, no live link is available, and no email was sent. The owner needs to
review/commit these docs, choose a GitHub destination, push and verify its URL, and supply the
roll number for the required lowercase email subject.

## Owner's exact remaining actions

1. Run `git status --short` and review the Phase 7 documentation changes.
2. Stage and commit the desired submission files, for example:
   `git add .gitignore README.md docs project_management && git commit -m "docs: prepare ScoreMe submission"`.
3. Create/select the GitHub repository and add its URL as `origin`, for example:
   `git remote add origin https://github.com/<account>/<repository>.git`.
4. Push the intended branch with `git push -u origin main` and open the URL to verify the
   repository contents. This workspace currently has no remote.
5. Replace `rollno` in `assignment_mnnit_scoreme_rollno` with the actual roll number. Email
   `it@scoreme.in` with the verified GitHub URL and link or attach `docs/ASSIGNMENT_REPORT.md`.
6. Confirm ScoreMe's applicable date/time for its stated 7:00 PM deadline.

## Known limitations

- Provider effects are at-least-once across a crash after external success and before local
  commit; exactly-once effects are not claimed.
- SQLite serializes writers; one retry worker is supported and its leases have no heartbeat.
- Admin access is a shared demo token, not production authentication/RBAC. Audit and
  explanation reads are request-ID scoped and unauthenticated in this MVP.
- Additive SQLite startup schema handling is used; Alembic is deferred.
- One upstream Starlette TestClient/httpx deprecation warning remains.
- The ignored developer `flowguard.db` contains one APPROVED request and three config
  snapshots. Final Phase 7 install/tests/smoke used no persistent database URL; do not delete
  or modify the existing file without confirming ownership.
