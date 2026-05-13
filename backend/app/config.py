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
    FRED_API_KEY: str = ""
    FMP_API_KEY: str = ""
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://pead:changeme@localhost:5432/pead_trading"
    # Phase 6 backtest gate override (use only with explicit human review — see runbook)
    BACKTEST_OVERRIDE_GATE_PASS: bool = False


settings = Settings()
