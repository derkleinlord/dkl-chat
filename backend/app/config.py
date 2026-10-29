from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://dklchat:change-me@127.0.0.1:3306/dklchat?charset=utf8mb4"
    secret_key: str = "development-only-change-this-secret"
    invite_codes: str = "FREUNDE2026"
    cookie_secure: bool = False
    allowed_origins: str = "http://localhost:5173,http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def invites(self) -> set[str]:
        return {item.strip() for item in self.invite_codes.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

