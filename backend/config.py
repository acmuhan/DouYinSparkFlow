from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    database_url: str = "mysql://sparkflow:sparkflow@127.0.0.1:3307/sparkflow"
    app_url: str = "http://localhost:3000"
    environment: str = "development"
    encryption_key: str = ""
    session_days: int = 14
    registration_enabled: bool = True
    worker_enabled: bool = True
    worker_timeout: int = Field(default=300, ge=10, le=3600)
    auto_create_tables: bool = False
    auto_migrate: bool = True
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "SparkFlow Admin"
    web_origin: str = "http://localhost:3000"
    epay_url: str = ""
    epay_version: str = "V1"
    epay_pid: str = ""
    epay_key: str = ""
    epay_private_key: str = ""
    epay_public_key: str = ""
    epay_checkout_mode: str = "redirect"
    epay_timestamp_tolerance: int = 300

    @property
    def sqlalchemy_url(self):
        return self.database_url.replace("mysql://", "mysql+pymysql://", 1)

    @property
    def production(self):
        return self.environment == "production"


@lru_cache
def get_settings():
    return Settings()
