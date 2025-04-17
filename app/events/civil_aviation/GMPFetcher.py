import asyncio
from datetime import datetime, timedelta
from typing import List

import httpx
from botpy import logging

from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo
from app.events.civil_aviation.utils.filters import flight_filter
from app.utils.time_utils import get_now, get_offset_from_str

logger = logging.get_logger()

headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}


class GMPFetcher:
    airport_name = '首尔金浦'
    airport_code = 'GMP'
    timezone = '+09:00'
    airports: dict = None
    fetch_lock = asyncio.Lock()
    api_url = 'https://www.airport.co.kr/gimpochn/ajaxf/frPryInfoSvc/getPryInfoList.do'
    supported_airlines = []
    supported_airports = []

    def now_time(self):
        return get_now(get_offset_from_str(self.timezone))

    def format_time(self, hour_min_str: str) -> str:
        if len(hour_min_str) == 4:
            return hour_min_str[0:2] + ':' + hour_min_str[2:]
        else:
            return hour_min_str

    def extract_airport(self, data):
        if (ap := data.get("ARRIVED_ENG")) and len(ap) >= 0:
            return ap
        if (ap := data.get("CITY")) and len(ap) >= 0:
            return ap
        return '未知'

    async def parse_dep_flight_data_from_row(self, data: dict):
        try:
            dep_time = self.format_time(data.get('STD'))
            ETD = self.format_time(data.get('ETD'))
            is_departed = (data.get("RMK_ENG") or "").strip() == 'DEPARTED'
            act_dep_time = ETD + '(实)' if ETD and is_departed else None
            estimated_dep_time = ETD
            if not act_dep_time and estimated_dep_time:
                act_dep_time = estimated_dep_time + "(预)"

            via_airports = []

            flight_date = datetime.strptime(data.get('ACT_C_DATE'), '%Y%m%d') if data.get('ACT_C_DATE') else None

            flight_info = FlightInfo(
                flight_no=data.get('AIR_FLN'),
                shared_codes=[],
                airlines=data.get('AIR_ENG', data.get('AIR_IATA')),
                airlines_code=data.get('AIR_IATA'),
                arr_airport=self.extract_airport(data),
                arr_airport_code=data.get('CITY'),
                via_airports=via_airports,
                dep_airport=self.airport_name,
                dep_airport_code=self.airport_code,
                dep_time=dep_time,
                act_dep_time=act_dep_time,
                date=flight_date,
                gate=data.get('GATE'),
                status=data.get('RMK_CHN'),
            )

            return flight_info
        except Exception as e:
            logger.warning(f"Parse flight error,err:{e} flight:{data}")

    async def parse_arr_flight_data_from_row(self, data: dict):
        arr_time = self.format_time(data.get('STD'))
        ETA = self.format_time(data.get('ETD'))
        is_arrived = (data.get("RMK_ENG") or "").strip() == 'ARRIVED'
        act_arr_time = ETA + '(实)' if ETA and is_arrived else None
        estimated_arr_time = ETA
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time + "(预)"

        via_airports = []

        flight_date = datetime.strptime(data.get('ACT_C_DATE'), '%Y%m%d') if data.get('ACT_C_DATE') else None

        flight_info = FlightInfo(
            flight_no=data.get('AIR_FLN'),
            shared_codes=[],
            airlines=data.get('AIR_ENG', data.get('AIR_IATA')),
            airlines_code=data.get('AIR_IATA'),
            arr_airport=self.airport_name,
            arr_airport_code=self.airport_code,
            via_airports=via_airports,
            dep_airport=self.extract_airport(data),
            dep_airport_code=data.get('CITY'),
            arr_time=arr_time,
            act_arr_time=act_arr_time,
            date=flight_date,
            carousel=data.get('GATE'),
            status=data.get('RMK_CHN'),
        )
        return flight_info

    def build_search_params(self, _form: QueryFlightForm, **kwargs):
        _now = self.now_time()
        today_date_str = _now.strftime("%Y%m%d")
        is_dep = kwargs.get('is_dep', True)
        return {
            "pInoutGbn": "O" if is_dep else "I",
            "pAirport": "GMP",
            "pActDate": today_date_str,
            "pSthourMin": _now.replace(minute=0, second=0).strftime("%H:%M"),
            "pEnhourMin": _now.replace(hour=23, minute=59, second=0).strftime("%H:%M"),
            "pCity": _form.airport or "",
            "pAirline": _form.airlines or "",
            "pAirlinenum": _form.flight_no or "",
            "p0": ""
        }

    async def fetch_flights(self, _form: QueryFlightForm, **kwargs):
        is_dep = True if not kwargs.get('arr') else False

        async def parse_flights(_flight_list: List[dict]):
            __flights: List[FlightInfo] = []
            if is_dep:
                return [await self.parse_dep_flight_data_from_row(x) for x in _flight_list]
            else:
                return [await self.parse_arr_flight_data_from_row(x) for x in _flight_list]

        try:
            flights: List[FlightInfo] = []
            max_result = kwargs.get('max_result', 20)
            async with httpx.AsyncClient() as client:
                _url = self.api_url
                params = self.build_search_params(_form, is_dep=is_dep)
                logger.info(f'fetching url:{_url} {params}')
                resp = await client.post(_url, headers=headers, data=params)
                resp.raise_for_status()
                raw_flight_list = resp.json().get('data', {}).get("list", [])
                _flights = await parse_flights(raw_flight_list)
                _flights = flight_filter(_flights, airlines_codes=_form.airlines_codes, airlines=_form.airlines,
                                         alliance=_form.alliance)
                flights.extend(_flights)

            flights = sorted(flights, key=lambda flight: flight.get_time(is_dep))
            flights = flights[0:max_result]
            return flights
        except Exception as e:
            logger.exception(e)
