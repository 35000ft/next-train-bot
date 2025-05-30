import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = (
    f"{os.getenv('DB_TYPE')}+aio{os.getenv('DB_TYPE')}://{os.getenv('DB_USER')}:{os.getenv('DB_PWD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
engine = create_async_engine(DATABASE_URL, echo=True)

async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

forbidden_words = os.getenv("FORBIDDEN_WORDS").split(',') if os.getenv("FORBIDDEN_WORDS") else []
accepted_wiki_topics = ['地铁', '未来公共运输建设', '地鐵', '鐵路', '铁路', '機場', '空运口岸', '交通',
                        '公共运输', '轨道', '国道', '机场', '客机', '航空器', '貨機', '地级市', '城市', '县份', '铁路',
                        '车站', '卫星', '電鐵', '道路', '公路', '气象', '氣候', '星座', '天文', '紅矮星', '天体',
                        '衛星', '市镇', '世界遗产', '历史文化名城']


class Config:
    TOKEN = os.getenv("BOT_TOKEN")
    APP_ID = os.getenv("APP_ID")
    DEV_MODE = os.getenv("DEV_MODE", False)
    SECRET = os.getenv("SECRET", False)


def get_db_session() -> AsyncSession:
    return async_session()
