# Decision and Versioning Examples

## Approved loan

Input: age 24, monthly income 60,000, credit score 750. Under either loan version, the
configured eligibility rules pass. The identity verification stage succeeds and the terminal
stage records `APPROVED`. The explanation includes the pinned config version, three persisted
rule traces, stage results and external verification attempt.

## Rejected loan

Input: age 17, monthly income 60,000, credit score 750. Rule `minimum_age` fails with action
`REJECT`; the configured transition reaches the rejected terminal stage. The explanation
identifies the failed rule and its persisted actual/expected values. No later rules are
re-evaluated when the workflow definition changes.

## Manual review

Input: age 24, monthly income 60,000, credit score 710 under loan v2. The 720 credit rule
fails with action `MANUAL_REVIEW`. The request status is pending, and the explanation has no
final `decision_outcome`. An authenticated reviewer resolves it with `APPROVE` or `REJECT` and
a required reason. The held Decision is updated in place; prior traces and external results
remain available. The review action, status transition and audit event commit atomically.

## Version change: score 710

Use a local admin token in PowerShell before starting the API:

```powershell
$env:FLOWGUARD_ADMIN_TOKEN = "local-demo-token-change-me"
```

Then use Swagger at `/docs` or the following sequence:

1. `POST /api/v1/admin/workflows/activate` with `{"workflow_id":"loan_approval","version":1}`.
2. Submit score 710 with a fresh `Idempotency-Key`, then explicitly execute it. The response
   is `APPROVED`, with `config_version: 1`.
3. Activate loan version 2 using the same endpoint.
4. Submit the same score with a different idempotency key, then execute. The response is
   `MANUAL_REVIEW`, with `config_version: 2`.
5. Fetch the first request status or explanation. It remains pinned to version 1 and remains
   approved after the active version changes.

The first-time database selects the highest validated version once. On later startups, the
persisted active marker is preserved. New configuration files are validated and stored as
inactive versions; activation is explicit and creates an administrative audit row. Repeating
activation of the already-active version is a no-op.

## Audit and retry evidence

`GET /api/v1/requests/{id}/audit` returns actual persisted rows in ascending sequence order.
For an external timeout followed by recovery, the sequence includes `RETRY_SCHEDULED`,
`RETRY_STARTED`, a successful external-call event and the final decision transition. Stage
may be null on historical events where that field was not recorded. Config version always
reflects the request's immutable pin.
