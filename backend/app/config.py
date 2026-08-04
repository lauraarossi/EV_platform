from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str = "dev-secret-key"
    environment: str = "development"
    openweather_api_key: str = ""
    fuel_price_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
