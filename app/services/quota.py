from sqlalchemy import func
from app.models import UsageEvent, Subscription


def get_active_plan(db, tenant_id):
    sub = db.query(Subscription).filter_by(tenant_id=tenant_id).first()
    return sub.plan if sub else None


def get_current_usage(db, tenant_id, usage_type):
    total = (
        db.query(func.coalesce(func.sum(UsageEvent.quantity), 0))
        .filter_by(tenant_id=tenant_id, usage_type=usage_type)
        .scalar()
    )
    return total or 0


def get_usage_summary(db, tenant_id, usage_type):
    plan = get_active_plan(db, tenant_id)
    if plan is None:
        return {"used": 0, "limit": 0}
    limit = plan.api_call_limit if usage_type == "api_call" else plan.token_limit
    used = get_current_usage(db, tenant_id, usage_type)
    return {"used": used, "limit": limit}


def check_quota(db, tenant_id, usage_type, requested_quantity):
    """
    Boundary rule: a request that brings usage to EXACTLY the limit is
    allowed. Only a request that would push usage PAST the limit is
    rejected. At limit=1000: the call taking used from 999 to 1000
    succeeds; the next one (1000 -> 1001) is rejected.
    """
    plan = get_active_plan(db, tenant_id)
    if plan is None:
        return {
            "allowed": False,
            "status_code": 402,
            "reason": "No active subscription for this tenant. Upgrade or subscribe to continue.",
            "used": 0,
            "limit": 0,
        }

    limit = plan.api_call_limit if usage_type == "api_call" else plan.token_limit
    used = get_current_usage(db, tenant_id, usage_type)

    if used + requested_quantity > limit:
        return {
            "allowed": False,
            "status_code": 429,
            "reason": f"Usage quota exceeded for {usage_type}: {used}/{limit} used, this request needs {requested_quantity} more.",
            "used": used,
            "limit": limit,
        }

    return {"allowed": True, "status_code": None, "reason": None, "used": used, "limit": limit}
