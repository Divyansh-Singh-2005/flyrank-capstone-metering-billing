from pydantic import BaseModel
from typing import Literal, List


class GenerateRequest(BaseModel):
    tenant_id: int
    usage_type: Literal["api_call", "tokens"]
    quantity: int
    idempotency_key: str


class GenerateResponse(BaseModel):
    status: str
    usage_type: str
    quantity: int
    used: int
    limit: int
    duplicate: bool


class UsageSummary(BaseModel):
    usage_type: str
    used: int
    limit: int
    cost_dollars: str


class UsageResponse(BaseModel):
    tenant_id: int
    plan: str
    usage: List[UsageSummary]
