from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str = "dev-secret-key"
    environment: str = "development"

    # Comma-separated list of allowed browser origins for the SPA.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # A blunt shared password in front of everything. Superseded by real
    # accounts, but kept for shielding a preview deployment. Empty = off.
    app_username: str = "eevie"
    app_password: str = ""

    # --- accounts ---------------------------------------------------------
    # Sessions are signed with SECRET_KEY. Changing it logs everyone out,
    # which is the intended way to revoke every session at once.
    session_cookie_name: str = "eevie_session"
    session_days: int = 30
    # Cookies are only marked Secure outside development, or they would never
    # be sent over plain http on localhost.
    @property
    def cookie_secure(self) -> bool:
        return self.environment.lower() != "development"

    # Sign-in with Google. Leave the client id empty to hide the option
    # entirely rather than showing a button that cannot work.
    google_client_id: str = ""
    google_client_secret: str = ""

    # Set to false once you have an account, to stop anyone else signing up.
    allow_registration: bool = True

    # Where the hand-downloaded VCA zips live. Empty means "work it out from
    # the layout" — see services/vca_catalog.
    vca_data_dir: str = ""

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
