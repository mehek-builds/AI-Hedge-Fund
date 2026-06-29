from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://pead:changeme@localhost:5432/pead_trading"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_BACKEND_URL: str = "redis://localhost:6379/1"
    REDIS_PUB_URL: str = "redis://localhost:6379/2"
    PREFECT_API_URL: str = "http://localhost:4200/api"
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_PAPER: bool = True


settings = Settings()
