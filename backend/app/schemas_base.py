from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


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
            "address",
            "address_number",
            "address_complement",
            "neighborhood",
            "city",
            "state",
            "postal_code",
            "representative_name",
            "representative_role",
        } and isinstance(value, str):
            return value.strip()
        return value
