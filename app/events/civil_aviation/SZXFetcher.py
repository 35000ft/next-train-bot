import asyncio
from datetime import datetime
from typing import List

import httpx
from botpy import logging
from pydantic import BaseModel

from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo
from app.events.civil_aviation.utils.filters import flight_filter
from app.utils.time_utils import get_now

logger = logging.get_logger()

headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}


class SZXFetcher:
    airport_name = '深圳'
    airport_code = 'SZX'
    timezone = 'Asia/Shanghai'
    airports: dict = None
    fetch_lock = asyncio.Lock()
    api_url = 'https://www.szairport.com/szjchbjk/hbcx/flightInfo'

    async def parse_dep_flight_data_from_row(self, data: dict, flight_date: datetime) -> FlightInfo:
        dep_time = data.get('startSchemeTakeoffTime')
        arr_time = data.get('terminalSchemeLandinTime')
        act_dep_time = data.get('startRealTakeoffTime') + '(实)' if data.get('setoffTimeAct') else None
        estimated_dep_time = None
        if not act_dep_time and estimated_dep_time:
            act_dep_time = estimated_dep_time + "(预)"
        flight_no_list = [x.get("flightNo", None) for x in data.get('hbh', [])]
        flight_info_list = list(filter(lambda x: x is not None, flight_filter(flight_no_list)))
        if flight_info_list:
            main_flight_no = flight_no_list[0]
            share_codes = flight_info_list[1:]
        else:
            main_flight_no = None
            share_codes = []
        flight_info = FlightInfo(
            flight_no=main_flight_no,
            shared_codes=share_codes,
            aircraft_model=data.get('craftType'),
            arr_airport=data.get('terminalStationThreecharcode', '未知'),
            via_airports=[],
            dep_airport=self.airport_name,
            dep_airport_code=self.airport_code,
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            arr_time=arr_time,
            act_arr_time=data.get("terminalRealLandinTime"),
            date=flight_date,
            terminal=data.get('apot'),
            gate=data.get('gateCode'),
            status=data.get('fltNormalStatus'),
        )

        return flight_info

    async def parse_arr_flight_data_from_row(self, data: dict, flight_date: datetime) -> FlightInfo:
        dep_time = data.get('startSchemeTakeoffTime')
        arr_time = data.get('terminalSchemeLandinTime')
        act_arr_time = data.get('terminalRealLandinTimeterminalRealLandinTime') + '(实)' if data.get(
            'terminalRealLandinTime') else None
        estimated_arr_time = None
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time + "(预)"
        flight_no_list = [x.get("flightNo", None) for x in data.get('hbh', [])]
        flight_info_list = list(filter(lambda x: x is not None, flight_filter(flight_no_list)))
        if flight_info_list:
            main_flight_no = flight_no_list[0]
            share_codes = flight_info_list[1:]
        else:
            main_flight_no = None
            share_codes = []
        flight_info = FlightInfo(
            flight_no=main_flight_no,
            shared_codes=share_codes,
            aircraft_model=data.get('craftType'),
            dep_airport=data.get('startStationThreecharcode', '未知'),
            via_airports=[],
            arr_airport=self.airport_name,
            arr_airport_code=self.airport_code,
            dep_time=dep_time,
            act_dep_time=data.get("startRealTakeoffTime"),
            arr_time=arr_time,
            act_arr_time=act_arr_time,
            date=flight_date,
            terminal=data.get('apot'),
            carousel=data.get('blls'),
            status=data.get('fltNormalStatus'),
        )

        return flight_info

    def build_list_params(self, _form: QueryFlightForm, is_dep: bool, **kwargs):
        return {
            'type': 'cn',
            'flag': "D" if is_dep else "A",
            'currentDate': "1",
            'currentTime': "12",  # 12是全部 0是0至2点 以此类推
            'hbxx_hbh': kwargs.get(_form.flight_no, kwargs.get(_form.airport, "")),  # 航班号 或 城市
        }

    async def fetch_flights(self, _form: QueryFlightForm, **kwargs):
        is_dep = True if not kwargs.get('arr') else False
        now = get_now(480)
        flight_date = now

        async def parse_flights(_flight_list: List[dict]):
            __flights: List[FlightInfo] = []
            if is_dep:
                return [await self.parse_dep_flight_data_from_row(x, flight_date) for x in _flight_list]
            else:
                return [await self.parse_arr_flight_data_from_row(x, flight_date) for x in _flight_list]

        try:
            flights: List[FlightInfo] = []
            max_result = kwargs.get('max_result', 20)
            async with httpx.AsyncClient() as client:
                _url = self.api_url
                params = self.build_list_params(_form, is_dep)
                logger.info(f'fetching url:{_url}')
                resp = await client.get(_url, headers=headers, params=params)
                resp.raise_for_status()
                flight_list = resp.json().get('flightList', [])
                _flights = await parse_flights(flight_list)
                _flights = flight_filter(_flights, airlines_codes=_form.airlines_codes, airlines=_form.airlines,
                                         aircraft_models=_form.aircraft_models, alliance=_form.alliance)
                flights.extend(_flights)

            flights = sorted(flights, key=lambda flight: flight.get_time(is_dep))
            flights = flights[0:max_result]
            return flights
        except Exception as e:
            logger.exception(e)
