import stripe
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models import WebhookEvent
from app.services.billing_sync import (
    handle_checkout_completed,
    handle_subscription_updated,
    handle_subscription_deleted,
)

try:
    from stripe import SignatureVerificationError
except ImportError:
    from stripe.error import SignatureVerificationError

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    existing = db.query(WebhookEvent).filter_by(stripe_event_id=event["id"]).first()
    if existing:
        return {"status": "ignored", "reason": "duplicate event", "event_id": event["id"]}

    event_type = event["type"]
    data_object = event["data"]["object"].to_dict()

    if event_type == "checkout.session.completed":
        handle_checkout_completed(db, data_object)
    elif event_type == "customer.subscription.updated":
        handle_subscription_updated(db, data_object)
    elif event_type == "customer.subscription.deleted":
        handle_subscription_deleted(db, data_object)

    db.add(WebhookEvent(stripe_event_id=event["id"], event_type=event_type))
    db.commit()

    return {"status": "processed", "type": event_type, "event_id": event["id"]}
