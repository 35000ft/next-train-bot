from sqlalchemy import Column, Integer, String, DateTime, Table, ForeignKey, BigInteger, Text, TIMESTAMP, func
from sqlalchemy.orm import declarative_base, relationship

Line_Station = Table('tb_line_station', declarative_base().metadata,
                     Column('station_id', Integer, ForeignKey('tb_station.id')),
                     Column('line_id', Integer, ForeignKey('tb_line.id')),
                     Column('station_order', Integer),
                     )


class Line(declarative_base()):
    __tablename__ = 'tb_line'

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    en_name = Column(String, nullable=False)
    system_code = Column(String, nullable=False)
    color = Column(String, nullable=False)


class Station(declarative_base()):
    __tablename__ = 'tb_station'

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    en_name = Column(String, nullable=False)
    system_code = Column(String, nullable=False)
    location = Column(String, nullable=False)


class PersonalConfig(declarative_base()):
    __tablename__ = 'tb_personal_config'
    __table_args__ = {'schema': 'next_train_bot'}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True)
    category_key = Column(String(255), nullable=True)
    group_id = Column(String(128), nullable=True)
    user_id = Column(String(128), nullable=True)
    params = Column(Text, nullable=True)
    status = Column(Integer, nullable=True, server_default='1')
    create_time = Column(TIMESTAMP, server_default=func.now())
    update_time = Column(TIMESTAMP, onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<PersonalConfig(id={self.id}, name={self.name}, category_key={self.category_key})>"
