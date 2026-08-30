from app.models import Subscription, Plan


def get_plan_by_name(db, name):
    return db.query(Plan).filter_by(name=name).first()


def handle_checkout_completed(db, session_obj):
    tenant_id = int(session_obj["client_reference_id"])
    customer_id = session_obj.get("customer")
    subscription_id = session_obj.get("subscription")

    pro_plan = get_plan_by_name(db, "pro")
    sub = db.query(Subscription).filter_by(tenant_id=tenant_id).first()

    if sub:
        sub.plan_id = pro_plan.id
        sub.status = "active"
        sub.stripe_customer_id = customer_id
        sub.stripe_subscription_id = subscription_id
    else:
        sub = Subscription(
            tenant_id=tenant_id,
            plan_id=pro_plan.id,
            status="active",
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
        )
        db.add(sub)

    db.commit()
    return sub


def handle_subscription_updated(db, sub_obj):
    customer_id = sub_obj.get("customer")
    status = sub_obj.get("status")

    sub = db.query(Subscription).filter_by(stripe_customer_id=customer_id).first()
    if not sub:
        return None

    sub.status = status
    db.commit()
    return sub


def handle_subscription_deleted(db, sub_obj):
    customer_id = sub_obj.get("customer")

    sub = db.query(Subscription).filter_by(stripe_customer_id=customer_id).first()
    if not sub:
        return None

    free_plan = get_plan_by_name(db, "free")
    sub.plan_id = free_plan.id
    sub.status = "canceled"
    db.commit()
    return sub
