from sqlalchemy.exc import IntegrityError
from app.models import UsageEvent


def get_existing_event(db, tenant_id, idempotency_key):
    return (
        db.query(UsageEvent)
        .filter_by(tenant_id=tenant_id, idempotency_key=idempotency_key)
        .first()
    )


def record_usage(db, tenant_id, usage_type, quantity, idempotency_key):
    """
    Insert a usage event exactly once per (tenant_id, idempotency_key).
    Returns (event, created). created=False means this was a duplicate
    retry and no new row was written.
    """
    existing = get_existing_event(db, tenant_id, idempotency_key)
    if existing:
        return existing, False

    event = UsageEvent(
        tenant_id=tenant_id,
        usage_type=usage_type,
        quantity=quantity,
        idempotency_key=idempotency_key,
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
        return event, True
    except IntegrityError:
        # A concurrent request with the same idempotency key won the
        # insert first. Roll back this attempt and return the winner's
        # row -- this is what makes it safe under real concurrency, not
        # just sequential retries.
        db.rollback()
        winner = get_existing_event(db, tenant_id, idempotency_key)
        return winner, False
