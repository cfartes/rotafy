from typing import Literal
from uuid import UUID

import phonenumbers
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
)

from app.documents import company_document

Role = Literal["admin", "attendant", "guide", "driver"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def trim_labels(cls, value, info: ValidationInfo):
        if info.field_name in {
            "full_name",
            "trade_name",
            "corporate_name",
            "company",
            "email",
            "cnpj",
            "name",
            "code",
        } and isinstance(value, str):
            return value.strip()
        return value


class Login(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    company: str | None = Field(default=None, max_length=50)


class UserCreate(Input):
    contact_phone: str | None = Field(default=None, max_length=50)

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value):
        return CompanyContact.validate_contact(value)

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Role = "attendant"


class CompanyContact(Input):
    contact_phone: str | None = Field(default=None, max_length=50)

    @field_validator("contact_phone")
    @classmethod
    def validate_contact(cls, value):
        if value is None or not value.strip():
            return None
        try:
            number = phonenumbers.parse(value.strip(), "BR")
        except phonenumbers.NumberParseException:
            raise ValueError(
                "Informe telefone/WhatsApp válido com DDD ou + e código do país."
            ) from None
        if not phonenumbers.is_valid_number(number) or number.extension:
            raise ValueError("Informe telefone/WhatsApp válido, sem ramal.")
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


class CompanyCreate(CompanyContact):
    contact_phone: str = Field(min_length=1, max_length=50)
    operational_profile: Literal["tourism", "regular"]
    slug: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9]+$")
    trade_name: str = Field(min_length=2, max_length=150)
    corporate_name: str = Field(min_length=2, max_length=150)
    cnpj: str
    plan_id: UUID
    primary_color: str = Field(default="#0A2540", pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str = Field(default="#FF6B4A", pattern=r"^#[0-9a-fA-F]{6}$")
    admin: UserCreate

    @field_validator("contact_phone")
    @classmethod
    def require_contact(cls, value):
        if not value:
            raise ValueError("Informe o telefone/WhatsApp da empresa.")
        return value

    @field_validator("cnpj")
    @classmethod
    def validate_cnpj(cls, value: str | None) -> str | None:
        result = company_document(value)
        if not result:
            raise ValueError("Informe o CPF/CNPJ da empresa para cobrança.")
        return result


class ActiveUpdate(Input):
    is_active: bool


class CompanyDetailsUpdate(CompanyContact):
    operational_profile: Literal["tourism", "regular"] | None = None
    expected_profile: Literal["tourism", "regular"] | None = None
    slug: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    trade_name: str = Field(min_length=2, max_length=150)
    corporate_name: str = Field(min_length=2, max_length=150)
    cnpj: str

    @field_validator("cnpj")
    @classmethod
    def validate_document(cls, value: str | None) -> str | None:
        result = company_document(value)
        if not result:
            raise ValueError("Informe o CPF/CNPJ da empresa para cobrança.")
        return result


class BrandingUpdate(Input):
    trade_name: str = Field(min_length=2, max_length=150)
    corporate_name: str = Field(min_length=2, max_length=150)
    primary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class UserUpdate(Input):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    role: Role | None = None
    is_active: bool | None = None


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class ResetRedeem(Input):
    token: str = Field(min_length=40, max_length=160)
    new_password: str = Field(min_length=12, max_length=128)


class UserView(BaseModel):
    contact_phone: str | None = None
    id: UUID
    company_id: UUID | None = None
    full_name: str
    email: str
    role: str
    is_active: bool
