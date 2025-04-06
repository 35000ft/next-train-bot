import time
from datetime import datetime
import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, Table, ForeignKey, BigInteger, Text, TIMESTAMP, func, \
    UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship


class RobotConfig(declarative_base()):
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
