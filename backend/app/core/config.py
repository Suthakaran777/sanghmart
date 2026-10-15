import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Sangh Mart"
    BILL_HEADER: str = "Sangh Mart"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sangh-mart-super-secret-key-change-in-production-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Defaults to SQLite async for local dev / tests, or Supabase PostgreSQL asyncpg in production
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./sanghmart.db")
    
    # UPI and settings defaults
    UPI_ID: str = os.getenv("UPI_ID", "asuthakaran2006@oksbi")
    BILL_PREFIX: str = "SM"
    BILL_YEAR: str = "2026"
    
    class Config:
        env_file = ".env"

settings = Settings()
