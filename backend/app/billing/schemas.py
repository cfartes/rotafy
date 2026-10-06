from datetime import date
from uuid import UUID

from pydantic import Field

from app.schemas import Input


class PlanTerms(Input):
    name: str = Field(min_length=2, max_length=100)
    included_trips: int = Field(ge=0, le=1000000, strict=True)
    price_cents: int = Field(ge=0, le=1000000000, strict=True)
    extra_trip_cents: int = Field(ge=0, le=1000000000, strict=True)


class PlanCreate(PlanTerms):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SubscriptionCreate(Input):
    plan_id: UUID
    starts_on: date


class PlanChange(Input):
    plan_id: UUID
