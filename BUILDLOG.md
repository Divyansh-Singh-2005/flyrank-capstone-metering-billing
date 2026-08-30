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

## Stripe webhooks (no live account — self-signed simulator)
- Tested signature verification, checkout-completed sync, replay
  dedup, and subscription-deleted downgrade using simulate_webhook.py,
  which signs payloads with the same HMAC scheme Stripe uses
  (t=<timestamp>,v1=<hmac_sha256>) against a locally-chosen
  STRIPE_WEBHOOK_SECRET. No Stripe account or CLI was needed to verify
  this logic; a real account is only required to run the live
  POST /billing/checkout flow end-to-end in a browser.
- Bug found while testing: stripe-python''s Session/Subscription
  objects disable .get() (they raise AttributeError pointing at
  .to_dict()). Fixed by converting event["data"]["object"] to a plain
  dict in the webhook handler before passing it to billing_sync.py.
- Bug found while testing: after subscription.deleted downgraded a
  tenant to Free, GET /usage started 404ing. Root cause: get_active_plan
  filtered on status="active", but the canceled subscription''s status
  was "canceled". Fixed by removing that filter -- a tenant''s
  subscription row persists for their whole lifecycle, and status is
  now just an audit field, not a gate on whether they have a usable
  plan. Caught by actually re-running GET /usage after the cancel test
  instead of assuming it would work.
