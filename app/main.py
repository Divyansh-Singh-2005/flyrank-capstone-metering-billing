from fastapi import FastAPI
from app.database import Base, engine
from app.routers import usage, billing, webhooks

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Usage Metering & Billing Engine")

app.include_router(usage.router)
app.include_router(billing.router)
app.include_router(webhooks.router)

@app.get("/health")
def health():
    return {"status": "ok"}
