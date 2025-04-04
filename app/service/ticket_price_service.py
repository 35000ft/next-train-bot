import os
from typing import Dict

import pandas as pd
from async_lru import alru_cache
from botpy import logging

logger = logging.get_logger()


@alru_cache(maxsize=32, ttl=300)
async def get_station_prices(railsystem: str, from_station: str) -> Dict[str, str] | None:
    path = f"{os.getenv('WORK_DIR')}/data/ticket-prices/ticket_price_{railsystem}.xlsx"
    if not os.path.exists(path):
        return None
    df = pd.read_excel(path, index_col=0, header=0)
    station_series = df[from_station]
    s_dict = station_series.to_dict()
    return s_dict


async def query_ticket_price(railsystem: str, from_station: str, to_station: str):
    logger.info(f'query ticket price, {from_station}->{to_station}')
    price_dict: Dict[str, str] = await get_station_prices(railsystem, from_station)
    logger.info(f'{price_dict}')
    if not price_dict:
        return None
    return price_dict.get(to_station, None)


async def njmtr_daily_ticket_info():
    pass
