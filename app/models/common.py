import datetime as dt
import time
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP

from .base import Base


class RobotConfig(Base):
    __tablename__ = 'tb_robot_config'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    uni_key = Column(String(255), nullable=False)
    parent_uni_key = Column(String(255), nullable=True)
    params = Column(Text, nullable=True)
    status = Column(Integer, default=1, nullable=False)
    create_time = Column(TIMESTAMP, default=datetime.fromtimestamp(time.time(), dt.UTC), nullable=True)
    update_time = Column(TIMESTAMP, nullable=True)

    __table_args__ = {
        'schema': 'next_train_bot'
    }


class SearchIndex(Base):
    __tablename__ = 'tb_robot_config'
    id = Column(Integer, primary_key=True, autoincrement=True)
    partition = Column(String(255), nullable=False)
    keyword = Column(String(255), nullable=False)
    target_ids = Column(Text, nullable=True)
    create_time = Column(TIMESTAMP, default=datetime.fromtimestamp(time.time(), dt.UTC), nullable=True)
