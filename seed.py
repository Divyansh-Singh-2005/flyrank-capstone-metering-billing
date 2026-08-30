from app.database import SessionLocal, Base, engine
from app.models import Tenant, Plan, Subscription

Base.metadata.create_all(bind=engine)
db = SessionLocal()

def get_or_create_plan(name, api_call_limit, token_limit):
    plan = db.query(Plan).filter_by(name=name).first()
    if not plan:
        plan = Plan(name=name, api_call_limit=api_call_limit, token_limit=token_limit)
        db.add(plan)
        db.commit()
        db.refresh(plan)
        print(f"Created plan: {name} ({api_call_limit} calls, {token_limit} tokens)")
    else:
        print(f"Plan already exists: {name}")
    return plan

free_plan = get_or_create_plan("free", 1000, 100_000)
pro_plan = get_or_create_plan("pro", 50000, 5_000_000)

tenant = db.query(Tenant).filter_by(name="Demo Tenant").first()
if not tenant:
    tenant = Tenant(name="Demo Tenant")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    print("Created tenant: Demo Tenant")
else:
    print("Tenant already exists: Demo Tenant")

subscription = db.query(Subscription).filter_by(tenant_id=tenant.id).first()
if not subscription:
    subscription = Subscription(tenant_id=tenant.id, plan_id=free_plan.id, status="active")
    db.add(subscription)
    db.commit()
    print("Created subscription: Demo Tenant -> free plan")
else:
    print("Subscription already exists for Demo Tenant")

db.close()
print("Seed complete.")
