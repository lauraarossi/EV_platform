from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str = "dev-secret-key"
    environment: str = "development"

    # Comma-separated list of allowed browser origins for the SPA.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    openweather_api_key: str = ""
    fuel_price_api_key: str = ""

    @field_validator("database_url")
    @classmethod
    def use_psycopg3_driver(cls, v: str) -> str:
        """Managed Postgres providers (Railway, Heroku, Render) hand out URLs as
        `postgres://` or `postgresql://`. SQLAlchemy maps both to psycopg2, which
        we don't install — psycopg3 is the driver here — so pin the driver
        explicitly rather than failing at connect time.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
