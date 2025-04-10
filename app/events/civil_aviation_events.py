from typing import List

from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from tabulate import tabulate

from app.events.civil_aviation.HKGFetcher import HKGFetcher
from app.events.civil_aviation.NKGFetcher import NKGFetcher
from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo
from app.events.civil_aviation.ShanghaiFetcher import SHAFetcher, PVGFetcher

logger = logging.get_logger()


def get_airport_fetcher(code: str):
    code = code.upper()
    _dict = {
        '南京': lambda: NKGFetcher(),
        'NKG': lambda: NKGFetcher(),
        '香港': lambda: HKGFetcher(),
        'HKG': lambda: HKGFetcher(),
        'SHA': lambda: SHAFetcher(),
        'PVG': lambda: PVGFetcher(),
        '浦东': lambda: PVGFetcher(),
        '虹桥': lambda: SHAFetcher(),
        '上海': lambda: SHAFetcher(),
    }
    return _dict[code]()


async def handle_query_flight(message: GroupMessage | C2CMessage, airport: str = '南京', **kwargs):
    await message.reply(content=f'正在查询{airport}航班大屏中...', msg_seq=1)
    fetcher = get_airport_fetcher(airport)
    if not fetcher:
        await message.reply(content="不支持该机场哦")
        return
    aircraft_models_str: str | None = kwargs.get('at', None)
    aircraft_models = []
    if aircraft_models_str:
        aircraft_models = aircraft_models_str.strip().split(',')
        aircraft_models = [x.upper().strip() for x in aircraft_models]

    _form = QueryFlightForm(flight_no=kwargs.get('no'), airport=kwargs.get('ap'), airlines=kwargs.get('al'),
                            aircraft_models=aircraft_models)
    logger.info(f'_form:{_form}')
    is_dep = True if not kwargs.get('arr', False) else False

    try:
        flights: List[FlightInfo] = await fetcher.fetch_flights(_form, max_result=10, **kwargs)
    except Exception as e:
        logger.exception(e)
        await message.reply(content=f'查询{airport}航班大屏异常', msg_seq=2)
        return
    content = f"{airport}机场{'出发' if is_dep else '到达'}大屏:\n"
    headers = ['航班号', '时刻', '目的地' if is_dep else '出发地', '机型']

    def format_time(_flight: FlightInfo) -> str:
        if is_dep:
            schedule_time, act_time = _flight.dep_time, _flight.act_dep_time
        else:
            schedule_time, act_time = _flight.arr_time, _flight.act_arr_time
        if act_time:
            return f'{schedule_time or "--:--"}/{act_time or "--:--"}'
        else:
            return schedule_time or "--:--"

    table = [
        [
            flight.flight_no,
            format_time(flight),
            flight.arr_airport if is_dep else flight.dep_airport,
            flight.aircraft_model
        ]
        for flight in flights]
    content += tabulate(table, headers, tablefmt='simple')
    await message.reply(content=content, msg_seq=2)
