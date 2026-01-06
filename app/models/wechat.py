from sqlalchemy import Column, String, TIMESTAMP, func, Boolean, Integer, SmallInteger

from .base import Base

schema = 'next_train_bot'


class WechatArticle(Base):
    __tablename__ = 'tb_wechat_article'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    picurl = Column(String, nullable=True)
    group_id = Column(String, nullable=True)
    url = Column(String, nullable=True)
    is_active = Column(SmallInteger, nullable=False, default=True)
    create_time = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    __table_args__ = {
        'schema': schema
    }
