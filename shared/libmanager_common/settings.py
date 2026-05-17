from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "libmanager-service"
    service_port: int = 8600
    environment: str = "dev"

    postgres_dsn: str = "postgresql+psycopg://libmanager:libmanager@postgres:5432/libmanager"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "libmanager"
    minio_secret_key: str = "libmanager123"
    minio_bucket: str = "ebooks"

    jwt_secret: str = "libmanager-dev-secret"
    encryption_key: str = "libmanager-dev-encryption-key"

    search_target_seconds: float = 1.0
    checkout_target_seconds: float = 10.0
    catalog_capacity_target: int = 1_000_000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
