from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "vineyard_smart_iot"
    DB_USER: str = "vineyard_app"
    DB_PASSWORD: str

    GATEWAY_TOKEN: str
    GATEWAY_URL: str = "http://127.0.0.1:8765/command"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
