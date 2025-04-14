import asyncio
from datetime import datetime
from typing import List

import httpx
from botpy import logging
from pydantic import BaseModel

from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo

logger = logging.get_logger()

headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}


class Airport(BaseModel):
    country: str
    code: str
    description: str


class CANFetcher:
    airport_name = '广州'
    airport_code = 'CAN'
    timezone = 'Asia/Shanghai'
    airports: dict = None
    fetch_lock = asyncio.Lock()
    api_url = 'https://www.baiyunairport.com/byairport-flight/flight/list'
    search_url = 'https://www.baiyunairport.com/byairport-flight/flight/searchFlight'

    def parse_flight_time(self, _time_str) -> str | None:
        try:
            x = datetime.strptime(_time_str, '%Y-%m-%d %H:%M:%S')
            return x.strftime('%H:%M')
        except:
            logger.warning(f'Parsing time error, _time_str:{_time_str}')
            return None

    async def parse_dep_flight_data_from_row(self, data: dict):
        dep_time = self.parse_flight_time(data.get('setoffTimePlan'))
        arr_time = self.parse_flight_time(data.get('arriTimePlan'))
        act_dep_time = self.parse_flight_time(data.get('setoffTimeAct')) + '(实)' if data.get('setoffTimeAct') else None
        estimated_dep_time = self.parse_flight_time(data.get('setoffTimePred'))
        if not act_dep_time and estimated_dep_time:
            act_dep_time = estimated_dep_time + "(预)"
        via_airport = data.get('viaAirport')
        flight_date = datetime.strptime(data['flightDate'], '%Y-%m-%d').date() if data.get('flightDate') else None

        flight_info = FlightInfo(
            flight_no=data.get('flightNo'),
            shared_codes=data.get('shareFlight', []),
            airlines=data.get('airlineCn', data.get('airline')),
            aircraft_model=data.get('planeModle'),
            arr_airport=data.get('dstCityCn', data.get('dstCity', '未知')),
            arr_airport_code=data.get('dstCity'),
            via_airports=[via_airport] if via_airport else [],
            dep_airport=self.airport_name,
            dep_airport_code=self.airport_code,
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            arr_time=arr_time,
            date=flight_date,
            terminal=data.get('terminal'),
            gate=data.get('boardingGate'),
            status=data.get('flightStatusCn'),
        )

        return flight_info

    async def parse_arr_flight_data_from_row(self, data: dict):
        dep_time = self.parse_flight_time(data.get('setoffTimePlan'))
        arr_time = self.parse_flight_time(data.get('arriTimePlan'))
        act_arr_time = self.parse_flight_time(data.get('arriTimeAct')) + '(实)' if data.get('arriTimeAct') else None
        estimated_arr_time = self.parse_flight_time(data.get('arriTimePred'))
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time + "(预)"
        via_airport = data.get('viaAirport')
        flight_date = datetime.strptime(data['flightDate'], '%Y-%m-%d').date() if data.get('flightDate') else None

        flight_info = FlightInfo(
            flight_no=data.get('flightNo'),
            shared_codes=data.get('shareFlight', []),
            airlines=data.get('airlineCn', data.get('airline')),
            aircraft_model=data.get('planeModle'),
            dep_airport=data.get('orgCityCn', data.get('orgCity', '未知')),
            dep_airport_code=data.get('orgCity'),
            via_airports=[via_airport] if via_airport else [],
            arr_airport=self.airport_name,
            arr_airport_code=self.airport_code,
            dep_time=dep_time,
            act_arr_time=act_arr_time,
            arr_time=arr_time,
            date=flight_date,
            terminal=data.get('terminal'),
            carousel=data.get('baggageTable'),
            status=data.get('flightStatusCn'),
        )

        return flight_info

    def build_search_params(self, _form: QueryFlightForm, is_dep: bool, **kwargs):
        return {
            "keyword": _form.flight_no or _form.airport,
            "type": "2" if kwargs.get('cargo') else "1",  # 1:客机 2:货机
            "terminal": kwargs.get('t', "").upper(),
            "day": kwargs.get('day', 0),
            "depOrArr": "1" if is_dep else "2",
            "pageNum": kwargs.get('cur_page', 1),
            "pageSize": 15
        }

    def build_list_params(self, _form: QueryFlightForm, is_dep: bool, **kwargs):
        return {
            'day': 0,  # 今天
            'pageNum': kwargs.get('cur_page', 1),
            'pageSize': 15,
            'terminal': kwargs.get('t', "").upper(),
            'depOrArr': "1" if is_dep else "2",
            'type': "2" if kwargs.get('cargo') else "1",  # 1:客机 2:货机
        }

    async def fetch_flights(self, _form: QueryFlightForm, **kwargs):
        def filter_flights(__flights: List[FlightInfo]) -> List[FlightInfo]:
            _result: List[FlightInfo] = __flights
            if _form.airlines:
                _result = filter(lambda x: _form.airlines in x.airlines if x.flight_no else False, list(_result))
            return list(_result)

        is_dep = True if not kwargs.get('arr') else False
        params = self.build_list_params(_form, is_dep, cur_page=1)

        # TODO
        max_fetch_page = kwargs.get('max_fetch_page', 3)
        fetched_page_count = 0

        async def handle_response(_j_obj):
            _flights: List[FlightInfo] = []

            _list = _j_obj['data'].get('list', [])
            if is_dep:
                _flights.extend([await self.parse_dep_flight_data_from_row(x) for x in _list])
            else:
                _flights.extend([await self.parse_arr_flight_data_from_row(x) for x in _list])

            _flights = filter_flights(_flights)
            max_result = kwargs.get('max_result', 20)
            _flights = _flights[0:max_result]
            flights_sorted = sorted(_flights, key=lambda flight: flight.get_time(is_dep))
            return flights_sorted

        try:
            logger.info(f'fetching url:{self.api_url}')
            flights: List[FlightInfo] = []
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.api_url, headers=headers, json=params)
                resp.raise_for_status()
                j_obj = resp.json()
                total_page = j_obj.get('pages', 1)
                cur_page = j_obj.get('pageNum', 1)
                while cur_page <= total_page and fetched_page_count < max_fetch_page:
                    flights.extend(await handle_response(j_obj))
                    cur_page += 1
                    fetched_page_count += 1
        except Exception as e:
            logger.exception(e)
