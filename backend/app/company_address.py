"""Company address validation and compatible partial updates."""

import re

from pydantic import Field, field_validator
from sqlalchemy import text

from app.schemas_base import Input

ADDRESS_FIELDS = (
    "address",
    "address_number",
    "address_complement",
    "neighborhood",
    "city",
    "state",
    "postal_code",
)
STATES = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}


class AddressInput(Input):
    @field_validator(*ADDRESS_FIELDS, mode="before")
    @classmethod
    def empty_address(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    address: str | None = Field(default=None, min_length=2, max_length=250)
    address_number: str | None = Field(default=None, min_length=1, max_length=30)
    address_complement: str | None = Field(default=None, max_length=150)
    neighborhood: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=9)

    @field_validator("state")
    @classmethod
    def valid_state(cls, value):
        if value is None:
            return None
        value = value.upper()
        if value not in STATES:
            raise ValueError("Informe uma UF brasileira válida.")
        return value

    @field_validator("postal_code")
    @classmethod
    def valid_postal(cls, value):
        if value is None:
            return None
        value = value.replace("-", "")
        if not re.fullmatch(r"[0-9]{8}", value):
            raise ValueError("Informe o CEP com oito dígitos.")
        return value


def complete_address(values):
    return all(values.get(k) for k in ADDRESS_FIELDS if k != "address_complement")


async def update_address(db, company_id, payload):
    values = {
        k: getattr(payload, k) for k in ADDRESS_FIELDS if k in payload.model_fields_set
    }
    if values:
        await db.execute(
            text(
                "UPDATE companies SET "
                + ",".join(f"{k}=:{k}" for k in values)
                + " WHERE id=:id"
            ),
            values | {"id": company_id},
        )
