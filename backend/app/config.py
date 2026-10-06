from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = Field(repr=False)
    platform_database_url: str = Field(repr=False)
    cookie_secure: bool = True
    allowed_origins: str = "https://frotafy.nexusdataanalytics.com.br"
    session_hours: int = 8
    resend_api_key: str = Field(default="", repr=False)
    email_from: str = ""
    public_base_url: str = "https://frotafy.nexusdataanalytics.com.br"

    @property
    def origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]
