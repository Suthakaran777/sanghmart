from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

import urllib.parse

# Handle standard postgres:// -> postgresql+asyncpg:// url conversion for Railway/Supabase
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Handle special characters (like @) in password if present
if "@" in db_url and "://" in db_url and db_url.startswith("postgresql+asyncpg://"):
    try:
        scheme, rest = db_url.split("://", 1)
        at_parts = rest.rsplit("@", 1)
        userinfo = at_parts[0]
        host_part = at_parts[1]
        if ":" in userinfo:
            user, pwd = userinfo.split(":", 1)
            pwd = urllib.parse.unquote(pwd)
            db_url = f"{scheme}://{user}:{urllib.parse.quote_plus(pwd)}@{host_part}"
    except Exception:
        pass

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
