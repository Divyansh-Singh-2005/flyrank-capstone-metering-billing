from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import GenerateRequest, GenerateResponse, UsageResponse, UsageSummary
from app.services.metering import record_usage, get_existing_event
from app.services.quota import check_quota, get_usage_summary, get_active_plan

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
def generate(payload: GenerateRequest, db: Session = Depends(get_db)):
    # Idempotency check runs BEFORE quota check. A retry of an
    # already-succeeded request must return the original result, not be
    # re-evaluated against current usage (which may have since changed).
    existing = get_existing_event(db, payload.tenant_id, payload.idempotency_key)
    if existing:
        summary = get_usage_summary(db, payload.tenant_id, existing.usage_type)
        return GenerateResponse(
            status="ok",
            usage_type=existing.usage_type,
            quantity=existing.quantity,
            used=summary["used"],
            limit=summary["limit"],
            duplicate=True,
        )

    quota = check_quota(db, payload.tenant_id, payload.usage_type, payload.quantity)
    if not quota["allowed"]:
        raise HTTPException(status_code=quota["status_code"], detail=quota["reason"])

    event, created = record_usage(
        db, payload.tenant_id, payload.usage_type, payload.quantity, payload.idempotency_key
    )
    summary = get_usage_summary(db, payload.tenant_id, event.usage_type)

    return GenerateResponse(
        status="ok",
        usage_type=event.usage_type,
        quantity=event.quantity,
        used=summary["used"],
        limit=summary["limit"],
        duplicate=not created,
    )


@router.get("/usage", response_model=UsageResponse)
def get_usage(tenant_id: int, db: Session = Depends(get_db)):
    plan = get_active_plan(db, tenant_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="No active subscription found for tenant.")

    api_summary = get_usage_summary(db, tenant_id, "api_call")
    token_summary = get_usage_summary(db, tenant_id, "tokens")

    return UsageResponse(
        tenant_id=tenant_id,
        plan=plan.name,
        usage=[
            UsageSummary(usage_type="api_call", used=api_summary["used"], limit=api_summary["limit"]),
            UsageSummary(usage_type="tokens", used=token_summary["used"], limit=token_summary["limit"]),
        ],
    )
