from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "groupsapp-auth"
    environment: str = "dev"

    api_host: str = "0.0.0.0"
    api_port: int = 8081
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50052

    database_url: str = "postgresql+asyncpg://groupsapp:groupsapp@localhost:5432/groupsapp_auth"

    jwt_secret_key: str = "change-me-in-production"
    jwt_issuer: str = "groupsapp-auth"
    access_token_ttl_seconds: int = 3600
    password_pbkdf2_iterations: int = 310000

    rabbitmq_url: str | None = None
    rabbitmq_exchange: str = "groupsapp.events"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
