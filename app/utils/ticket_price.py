import os
from typing import Dict

import pandas as pd


async def get_station_prices(railsystem: str, from_station) -> Dict[str, str] | None:
    path = f"{os.getenv('WORK_DIR')}/data/ticket_price_{railsystem}.xlsx"
    if not os.path.exists(path):
        return None
    df = pd.read_excel(path, index_col=0, header=0)
    station_series = df[from_station]
    s_dict = station_series.to_dict()
    return s_dict


async def query_ticket_price(railsystem: str, from_station: str, to_station: str):
    price_dict: Dict[str, str] = await get_station_prices(railsystem, from_station)
    if not price_dict:
        return None
    return price_dict.get(to_station, None)
