from sqlalchemy import Column, Integer, String, DateTime, Table, ForeignKey
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
