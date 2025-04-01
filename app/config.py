from dotenv import load_dotenv
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = (
    f"{os.getenv('DB_TYPE')}+aio{os.getenv('DB_TYPE')}://{os.getenv('DB_USER')}:{os.getenv('DB_PWD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
engine = create_async_engine(DATABASE_URL, echo=True)

async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Config:
    TOKEN = os.getenv("BOT_TOKEN")
    APP_ID = os.getenv("APP_ID")
    DEV_MODE = os.getenv("DEV_MODE", False)
    SECRET = os.getenv("SECRET", False)


def get_db_session() -> AsyncSession:
    return async_session()
