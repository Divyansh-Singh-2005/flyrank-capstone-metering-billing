import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models import Tenant

router = APIRouter()
stripe.api_key = settings.stripe_secret_key


@router.post("/billing/checkout")
def create_checkout_session(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_PRICE_ID_PRO to enable live checkout.",
        )

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id_pro, "quantity": 1}],
        client_reference_id=str(tenant_id),
        success_url="http://localhost:8000/billing/success",
        cancel_url="http://localhost:8000/billing/cancel",
    )
    return {"checkout_url": session.url}
