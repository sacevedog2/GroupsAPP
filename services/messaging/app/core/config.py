from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "groupsapp-messaging"
    environment: str = "dev"

    api_host: str = "0.0.0.0"
    api_port: int = 8080
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051

    database_url: str = "sqlite+aiosqlite:///./data/messaging.db"

    rabbitmq_url: str | None = None
    rabbitmq_exchange: str = "groupsapp.events"

    attachment_root: str = "./data/attachments"
    max_upload_mb: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
