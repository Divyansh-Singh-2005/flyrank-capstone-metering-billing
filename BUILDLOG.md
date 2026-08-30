# Build Log

## Metering & quota (POST /generate, GET /usage)
- AI helped scaffold the idempotency pattern: check-then-insert with a
  UniqueConstraint(tenant_id, idempotency_key) as the DB-level backstop,
  and an IntegrityError catch for the race where two retries insert
  concurrently. I chose to check idempotency BEFORE quota so a retry of
  an already-successful request always succeeds, even if quota filled
  up in between -- that ordering decision was mine, not suggested.
- 402 vs 429 split: 402 = no active subscription at all; 429 = valid
  subscription but over its usage cap. This is one reasonable
  interpretation of the brief; documented here since the brief leaves
  the exact split up to the builder.
- Verified manually via PowerShell Invoke-RestMethod: same
  idempotency_key sent twice returns duplicate=true on the second call
  with no change in `used`; quota boundary at exactly 1000/1000 allows
  the request that reaches the limit and rejects the next one with 429.
