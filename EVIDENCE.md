# EVIDENCE.md

One pasted proof per Requirements checkbox (Section 6 of the brief).
All commands run locally via `uvicorn app.main:app --reload` +
PowerShell `Invoke-RestMethod` / `python simulate_webhook.py`.

## Metering: exactly-once via idempotency key

Same idempotency_key ("idem-test-1") sent twice. First call creates
the event; second call returns the original result unchanged.

    PS> $body = @{ tenant_id = 1; usage_type = "api_call"; quantity = 1; idempotency_key = "idem-test-1" } | ConvertTo-Json
    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/generate" -Method Post -Body $body -ContentType "application/json"
    status     : ok
    usage_type : api_call
    quantity   : 1
    used       : 1
    limit      : 1000
    duplicate  : False

    PS> # ... later, after used had climbed to exactly 1000/1000 (quota full) ...
    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/generate" -Method Post -Body $body -ContentType "application/json"
    status     : ok
    usage_type : api_call
    quantity   : 1
    used       : 1000
    limit      : 1000
    duplicate  : True

Second call correctly returns duplicate=True with `used` unchanged --
proving the retry did not create a second row, and that idempotency
is honored even when quota is completely exhausted (checked before
the quota gate, by design).

## Quotas: boundary honesty (429) and clear message

Free plan limit is 1000 api_call/month. A request bringing usage to
exactly 1000 succeeds; the next unit is rejected with 429 and an
explanation.

    PS> $body = @{ tenant_id = 1; usage_type = "api_call"; quantity = 999; idempotency_key = "boundary-fill" } | ConvertTo-Json
    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/generate" -Method Post -Body $body -ContentType "application/json"
    status     : ok
    usage_type : api_call
    quantity   : 999
    used       : 1000
    limit      : 1000
    duplicate  : False

    PS> $body = @{ tenant_id = 1; usage_type = "api_call"; quantity = 1; idempotency_key = "boundary-over" } | ConvertTo-Json
    PS> try { Invoke-RestMethod -Uri "http://127.0.0.1:8000/generate" -Method Post -Body $body -ContentType "application/json" }
    >> catch { Write-Host "Status:" $_.Exception.Response.StatusCode.value__; Write-Host $_.ErrorDetails.Message }
    Status: 429
    {"detail":"Usage quota exceeded for api_call: 1000/1000 used, this request needs 1 more."}

    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/usage?tenant_id=1"
    tenant_id plan usage
    --------- ---- -----
            1 free {@{usage_type=api_call; used=1000; limit=1000}, @{usage_type=tokens; used=0; limit=100000}}

## Cost calculation: AI-token pricing rules

Standalone proof script (`prove_pricing.py`) verifies calculated
totals against hand-worked expected values for four cases, including
cached-input-is-cheaper and reasoning-tokens-bill-as-output.

    PS> python prove_pricing.py
    Pinned rates (micro-cents per token):
      input: 300
      cached_input: 75
      output: 1500

    Case 1: 1000 input, 500 output
      calculated total_microcents = 1050000
      hand-calculated expected    = 1050000
      match: True

    Case 2: 1000 fresh input vs 1000 cached input
      fresh input cost microcents  = 300000
      cached input cost microcents = 75000
      cached is cheaper: True

    Case 3: 200 output + 300 reasoning tokens
      billable_output_tokens      = 500 (expected 500)
      calculated total_microcents = 750000
      hand-calculated expected    = 750000
      match: True

    Case 4: 1000 input, 2000 cached input, 300 output, 150 reasoning
      calculated total_microcents = 1125000
      hand-calculated expected    = 1125000
      match: True
      total_dollars = $1.125000

Wired into the live API -- GET /usage returns a real dollar figure
for metered token usage:

    PS> $body = @{ tenant_id = 1; usage_type = "tokens"; quantity = 2500; idempotency_key = "cost-test-1" } | ConvertTo-Json
    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/generate" -Method Post -Body $body -ContentType "application/json"
    status     : ok
    usage_type : tokens
    quantity   : 2500
    used       : 2500
    limit      : 100000
    duplicate  : False

    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/usage?tenant_id=1" | ConvertTo-Json -Depth 5
    {
        "tenant_id":  1,
        "plan":  "free",
        "usage":  [
                      { "usage_type": "api_call", "used": 0, "limit": 1000, "cost_dollars": "$0.000000" },
                      { "usage_type": "tokens", "used": 2500, "limit": 100000, "cost_dollars": "$3.750000" }
                  ]
    }

2500 tokens x 1500 micro-cents / 1,000,000 = $3.750000. Matches.

## Stripe: signature verification, dedup, and plan sync

Tested offline via `simulate_webhook.py`, which signs synthetic
events with the same HMAC scheme Stripe uses
(t=<timestamp>,v1=<hmac_sha256>) against a locally-chosen
STRIPE_WEBHOOK_SECRET.

Forged signature is rejected with 400, nothing changes:

    PS> python simulate_webhook.py bad_signature --tenant-id 1
    Status: 400
    {"detail":"Invalid webhook signature"}

checkout.session.completed flips the tenant Free -> Pro:

    PS> python simulate_webhook.py checkout_completed --tenant-id 1 --customer cus_demo123 --subscription sub_demo123
    Status: 200
    {"status":"processed","type":"checkout.session.completed","event_id":"evt_test_df51f5920d36481a89eea0ea"}

    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/usage?tenant_id=1"
    tenant_id plan usage
    --------- ---- -----
            1 pro  {@{usage_type=api_call; used=0; limit=50000}, @{usage_type=tokens; used=0; limit=5000000}}

Same event replayed (same event_id) is processed once, ignored on
replay:

    PS> python simulate_webhook.py replay --tenant-id 1
    --- First send ---
    Status: 200
    {"status":"processed","type":"checkout.session.completed","event_id":"evt_test_5482b110d9ab4c6b8741c2af"}
    --- Replay (same event id) ---
    Status: 200
    {"status":"ignored","reason":"duplicate event","event_id":"evt_test_5482b110d9ab4c6b8741c2af"}

customer.subscription.deleted downgrades the tenant back to Free:

    PS> python simulate_webhook.py sub_deleted --customer cus_demo123
    Status: 200
    {"status":"processed","type":"customer.subscription.deleted","event_id":"evt_test_beb8076550ef4e32ba68efb3"}

    PS> Invoke-RestMethod -Uri "http://127.0.0.1:8000/usage?tenant_id=1"
    tenant_id plan usage
    --------- ---- -----
            1 free {@{usage_type=api_call; used=0; limit=1000}, @{usage_type=tokens; used=0; limit=100000}}

## Data model, tenant isolation

Schema defined in app/models.py: Tenant, Plan, Subscription,
UsageEvent, WebhookEvent. UsageEvent carries a tenant_id foreign key
and every query in app/services/quota.py and app/services/metering.py
filters by tenant_id, so one tenant''s usage/quota state cannot leak
into another''s calculations. Not yet covered: an automated test
proving cross-tenant isolation under concurrent load (noted as a
limitation in README.md).
