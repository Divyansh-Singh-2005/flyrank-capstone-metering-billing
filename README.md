# Usage Metering & Billing Engine

A backend service answering the three questions every SaaS needs:
how much has a customer used, what does it cost, and have they hit
their plan limit. Built with FastAPI + SQLite. Idempotent metering,
quota enforcement, integer-cents money math, and Stripe test-mode
subscription sync via signature-verified, deduplicated webhooks.

## Architecture

    Client -> POST /generate
      -> check idempotency_key (tenant_id, idempotency_key) unique
         | already exists? -> return original result, no new row
      -> check_quota(tenant, usage_type, qty)
         | over limit? -> 429 / 402 with explanation
      -> record_usage() -> insert usage_event (or catch IntegrityError
         on a concurrent duplicate insert and return the winner's row)

    Client -> GET /usage?tenant_id=X
      -> rollup usage_events -> { used, limit, cost_dollars } per type

    Stripe -> signed webhook -> POST /webhooks/stripe
      -> verify HMAC signature (bad sig -> 400)
      -> dedupe by stripe_event_id (replay -> ignored, processed once)
      -> checkout.session.completed  -> tenant upgraded to Pro
      -> customer.subscription.updated -> subscription status synced
      -> customer.subscription.deleted -> tenant downgraded to Free

## Setup and run (clean machine)

    git clone https://github.com/Divyansh-Singh-2005/flyrank-capstone-metering-billing.git
    cd flyrank-capstone-metering-billing
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env
    python seed.py
    uvicorn app.main:app --reload

On macOS/Linux, use `source venv/bin/activate` and `cp .env.example .env` instead.

Visit `http://localhost:8000/docs` for interactive API docs, or `http://localhost:8000/health`.

Seeding creates: a `free` plan (1,000 API calls / 100,000 tokens per
month), a `pro` plan (50,000 API calls / 5,000,000 tokens per month),
and a demo tenant (`tenant_id=1`) on the free plan.

## Plans and quotas

| Plan | API calls / month | AI tokens / month |
|------|--------------------|--------------------|
| Free | 1,000              | 100,000            |
| Pro  | 50,000             | 5,000,000          |

## Design decisions

**Idempotency.** `(tenant_id, idempotency_key)` has a database-level
`UniqueConstraint`. A retry with the same key returns the original
event untouched -- checked before the quota check, so a retry of an
already-successful request always succeeds even if quota filled up in
the meantime. A concurrent duplicate insert raises `IntegrityError`,
which is caught and resolved by returning the row that won the race.

**402 vs 429.** `402 Payment Required` means no active subscription
exists for the tenant at all. `429 Too Many Requests` means a valid
subscription exists but the request would exceed its usage cap. A
request that brings usage to exactly the limit is allowed; only a
request that would push it past the limit is rejected.

**AI token pricing.** Rates are pinned in `app/services/pricing.py`
(micro-cents per token, to avoid float rounding on money): fresh
input tokens, cached input tokens (billed cheaper), and output
tokens. Reasoning tokens are billed at the output rate, added to
`output_tokens` -- never their own category, never free, never priced
at the input rate. Proof of correct totals: run `python
prove_pricing.py`. Token usage is simulated -- no AI model call is
made anywhere in this system.

**Stripe integration.** Signature verification, event dedup, and the
Free/Pro plan-sync logic are all implemented in
`app/routers/webhooks.py` and `app/services/billing_sync.py`, and are
fully testable without a live Stripe account: `simulate_webhook.py`
signs synthetic events with Stripe's documented HMAC scheme
(`t=<timestamp>,v1=<hmac_sha256>`) against a locally-chosen
`STRIPE_WEBHOOK_SECRET`, so signature checking, replay protection, and
the plan-flip logic are all verified end-to-end offline. The one part
that genuinely requires a real Stripe test-mode account and API key is
running `POST /billing/checkout` live in a browser -- the endpoint is
implemented and returns a clean `503` (not a raw crash) if
`STRIPE_SECRET_KEY` isn't configured.

## Limitations

- No automated test suite (pytest) yet -- verification so far is
  manual, transcript-evidenced testing (see `EVIDENCE.md`), which the
  brief allows but does not require.
- Live Stripe Checkout has not been run end-to-end against a real
  Stripe account; the webhook-side logic it depends on has been, via
  the offline simulator described above.
- Token pricing meters `tokens` as a single combined quantity per
  Section 7's 2-usage-type scope, billed at the output rate. A
  finer-grained system would record input/cached/output/reasoning as
  separate usage types to price each independently (the pricing
  function already supports this; the metering schema does not yet
  split them out).
- No overage billing, invoicing, or proration -- explicitly out of
  core scope per Section 7 of the brief.
