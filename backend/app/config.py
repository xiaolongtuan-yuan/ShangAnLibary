"""应用配置：全部来自环境变量，字段与默认值见 docs/api-contract.md §2。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://study:study123@db:5432/study"
    SECRET_KEY: str  # 必填，无默认值（JWT 与签名 URL 密钥）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    PDF_DATA_DIR: str = "/data/pdf"
    USE_X_ACCEL: bool = True
    INIT_ADMIN_USERNAME: str = "admin"
    INIT_ADMIN_PASSWORD: str | None = None
    INIT_ADMIN_EMAIL: str = "admin@example.com"
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS_ORIGINS 逗号分隔解析为列表，如 '*' -> ['*']。"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
