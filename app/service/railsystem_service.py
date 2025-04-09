import asyncio
import logging
import os

from typing import List, Dict, Optional

import httpx
from async_lru import alru_cache
from sqlalchemy import select, or_

from app.config import get_db_session
from app.models.Railsystem import Station
from app.schemas import RailsystemSchemas

nmtr_headers = {
    'accept': 'application/json,text/plain',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'X-SOURCE': F"NEXT-TRAIN-BOT@{os.getenv('APP_ID')}"
}
logger = logging.getLogger(__name__)


async def get_station_by_names(name_list: List[str], railsystem: str = None) -> Dict[str, List[Station] | Station]:
    async with get_db_session() as session:
        stmt = select(Station).where(Station.name.in_(name_list))
        # 如果 railsystem 不为空或空字符串，则加入额外条件
        if railsystem:
            stmt = stmt.where(Station.railsystem == railsystem)
        stmt = stmt.order_by(Station.name.asc(), Station.id.asc())

        result = await session.execute(stmt)
        stations = result.scalars().all()
        r_result = {}

        for name in name_list:
            # 根据站点名称进行过滤
            _stations = [station for station in stations if station.name == name]
            # 根据需要可进行进一步判断，这里示例：如果只有一个匹配项则直接返回单个对象
            if len(_stations) == 1:
                r_result[name] = _stations[0]
            elif len(_stations) == 0:
                r_result[name] = None
            else:
                r_result[name] = _stations

        return r_result


async def get_station_by_keyword(keyword: str, railsystem: str = None) -> List[Station] | Optional[Station]:
    async with get_db_session() as session:
        stmt = select(Station).where(or_(Station.name.ilike(f'%{keyword}%'), Station.code == keyword.upper()))
        # 如果 railsystem 不为空或空字符串，则加入额外条件
        if railsystem:
            stmt = stmt.where(Station.system_code == railsystem)
        stmt = stmt.order_by(Station.name.asc(), Station.id.asc())

        result = await session.execute(stmt)
        stations: List[Station] = result.scalars().all()
        if not stations:
            return None

        full_match = list(
            filter(lambda x: x.name.upper() == keyword.upper() or x.code.upper() == keyword.upper(), stations))
        if full_match:
            return full_match[0] if len(full_match) == 1 else full_match

        if len(stations) == 1:
            return stations[0]
        else:
            return stations


@alru_cache(maxsize=64, ttl=600)
async def get_station_detail_byid(station_id: str):
    logger.debug(f'station id:{station_id}')
    url = f'https://nmtr.online/file/railsystem/stations/id/{station_id}'
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url=url, headers=nmtr_headers)
            resp.raise_for_status()
            j_obj = resp.json()
            j_obj = j_obj['data'] if 'data' in j_obj else j_obj

            station = RailsystemSchemas.Station(**j_obj)
            return station
    except Exception as e:
        logger.warning(f'Get station detail error, station_id:{station_id} err:{e}')
        return None
