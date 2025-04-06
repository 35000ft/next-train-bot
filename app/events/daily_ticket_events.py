import random
from collections import defaultdict

from app.schemas import RailsystemSchemas
from typing import List, Dict, Tuple

from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.service.ticket_price_service import get_station_prices

logger = logging.get_logger()


async def handle_njmtr_daily_ticket(message: GroupMessage | C2CMessage, station: RailsystemSchemas.Station, **kwargs):
    station_prices: Dict[str, str] = await get_station_prices(station.railsystemCode, station.name)
    if not station_prices:
        await message.reply(content=f'无法获取车站:{station.name} 票价表')
        return
    one_day: List[Tuple[str, str]] = [item for item in station_prices.items() if float(item[1]) >= 10]
    three_day: List[Tuple[str, str]] = [item for item in station_prices.items() if float(item[1]) >= 7.5]

    def format_station_names(_station_names: List[Tuple[str, str]]) -> str:
        if not _station_names:
            return '无'

        # Group station names by ticket price (converted to float)
        groups = defaultdict(list)
        for _s, price in _station_names:
            price_val = float(price)
            groups[price_val].append(_s)

        # Sort groups by price (low to high) and then take first 5 station names for each group
        result_lines = []
        max_show_number = 5
        for price in sorted(groups.keys()):
            _temp = sorted(groups[price])
            stations = random.sample(_temp, min(len(_temp), max_show_number))
            row = f"{price}元: " + ", ".join(stations)
            if len(groups[price]) > max_show_number:
                row += f"...(共{len(groups[price])}个)"
            result_lines.append(row)

        return "\n".join(result_lines)

    daily_ticket_info = f"""车站:{station.name} (以下为单程票价，按每日往返计算) \n一日票回本方案:\n{format_station_names(one_day)}\n三日票回本方案:\n{format_station_names(three_day)}
    (一日票20元，三日票45元)"""
    await message.reply(content=daily_ticket_info, msg_seq=message.msg_seq or 1 + 1)
