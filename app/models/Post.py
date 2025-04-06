import time
import uuid
from datetime import datetime
import datetime as dt

from sqlalchemy import Column, Integer, String, DateTime, Table, ForeignKey, BigInteger, Text, TIMESTAMP, func, \
    UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship


class Post(declarative_base()):
    __tablename__ = 'tb_posts'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    post_type = Column(String, nullable=False, comment='投稿类型')
    post_id = Column(String, nullable=False, comment='投稿id')
    name = Column(String, nullable=False, comment='名称')
    file_path = Column(String, nullable=False, comment='文件路径')
    user_id = Column(Integer, nullable=False, comment='投稿人id')
    user_name = Column(String, nullable=False, comment='投稿人名称')
    create_time = Column(TIMESTAMP, default=datetime.fromtimestamp(time.time(), dt.UTC), nullable=True,
                         comment='创建时间')
    status = Column(Integer, default=0, nullable=False, comment='状态')

    __table_args__ = {
        'schema': 'next_train_bot',
        'comment': '投稿表',
    }
