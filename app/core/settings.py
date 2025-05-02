# app/core/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # Now importable as app.core.settings.settings
if __name__ == "__main__":
    print("Loaded DATABASE_URL =", settings.DATABASE_URL)
    print("Loaded SECRET_KEY length =", len(settings.SECRET_KEY))