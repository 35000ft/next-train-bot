from datetime import datetime, date

from pydantic import BaseModel
from typing import List


class Line(BaseModel):
    """地铁线路信息"""
    id: str
    name: str
    enName: str
    code: str
    color: str


class Station(BaseModel):
    """地铁站点信息"""
    id: str
    name: str
    enName: str
    code: str
    location: str
    railsystemCode: str
    railsystemName: str
    timezone: str
    lines: List[Line]


class TrainInfo(BaseModel):
    """列车信息"""
    arr: datetime  # 到达时间
    dep: datetime  # 出发时间
    trainDate: date  # 列车日期
    id: str
    terminal: str  # 终点站
    isFirstStop: bool  # 是否是首站
    trainType: str  # 列车类型
    trainInfoId: int  # 列车信息 ID
    isLastStop: bool  # 是否是末站
