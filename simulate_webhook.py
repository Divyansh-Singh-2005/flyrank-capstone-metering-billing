"""
Simulate signed Stripe webhook events for local testing without a live
Stripe account. Builds a JSON event payload shaped like Stripe's real
events, signs it with STRIPE_WEBHOOK_SECRET using Stripe's documented
HMAC scheme (t=<timestamp>,v1=<hmac>), and POSTs it to the local server.

Usage:
    python simulate_webhook.py checkout_completed --tenant-id 1
    python simulate_webhook.py sub_updated --customer cus_demo123 --status active
    python simulate_webhook.py sub_deleted --customer cus_demo123
    python simulate_webhook.py bad_signature --tenant-id 1
    python simulate_webhook.py replay --tenant-id 1
"""

import argparse
import hashlib
import hmac
import json
import time
import uuid

import httpx

from app.config import settings

WEBHOOK_URL = "http://127.0.0.1:8000/webhooks/stripe"


def sign_payload(payload_bytes: bytes, secret: str, timestamp: int) -> str:
    signed_payload = f"{timestamp}.{payload_bytes.decode('utf-8')}"
    signature = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def send_event(event: dict, bad_signature: bool = False):
    payload_bytes = json.dumps(event).encode("utf-8")
    timestamp = int(time.time())
    secret = "wrong_secret_on_purpose" if bad_signature else settings.stripe_webhook_secret
    sig_header = sign_payload(payload_bytes, secret, timestamp)

    response = httpx.post(
        WEBHOOK_URL,
        content=payload_bytes,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    print(f"Status: {response.status_code}")
    print(response.text)


def event_envelope(event_type: str, data_object: dict) -> dict:
    return {
        "id": f"evt_test_{uuid.uuid4().hex[:24]}",
        "object": "event",
        "type": event_type,
        "created": int(time.time()),
        "data": {"object": data_object},
    }


def checkout_completed(tenant_id, customer, subscription):
    session_obj = {
        "id": f"cs_test_{uuid.uuid4().hex[:24]}",
        "object": "checkout.session",
        "client_reference_id": str(tenant_id),
        "customer": customer,
        "subscription": subscription,
        "payment_status": "paid",
        "status": "complete",
    }
    return event_envelope("checkout.session.completed", session_obj)


def subscription_updated(customer, status):
    sub_obj = {"id": f"sub_test_{uuid.uuid4().hex[:24]}", "object": "subscription", "customer": customer, "status": status}
    return event_envelope("customer.subscription.updated", sub_obj)


def subscription_deleted(customer):
    sub_obj = {"id": f"sub_test_{uuid.uuid4().hex[:24]}", "object": "subscription", "customer": customer, "status": "canceled"}
    return event_envelope("customer.subscription.deleted", sub_obj)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["checkout_completed", "sub_updated", "sub_deleted", "bad_signature", "replay"])
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--customer", default="cus_demo123")
    parser.add_argument("--subscription", default="sub_demo123")
    parser.add_argument("--status", default="active")
    args = parser.parse_args()

    if args.command == "checkout_completed":
        send_event(checkout_completed(args.tenant_id, args.customer, args.subscription))
    elif args.command == "sub_updated":
        send_event(subscription_updated(args.customer, args.status))
    elif args.command == "sub_deleted":
        send_event(subscription_deleted(args.customer))
    elif args.command == "bad_signature":
        send_event(checkout_completed(args.tenant_id, args.customer, args.subscription), bad_signature=True)
    elif args.command == "replay":
        event = checkout_completed(args.tenant_id, args.customer, args.subscription)
        print("--- First send ---")
        send_event(event)
        print("--- Replay (same event id) ---")
        send_event(event)
