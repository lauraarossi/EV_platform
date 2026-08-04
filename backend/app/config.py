from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str = "dev-secret-key"
    environment: str = "development"
    openweather_api_key: str = ""
    fuel_price_api_key: str = ""


settings = Settings()
