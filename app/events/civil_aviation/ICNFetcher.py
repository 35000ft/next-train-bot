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


class ICNFetcher:
    airport_name = '首尔仁川'
    airport_code = 'ICN'
    timezone = '+09:00'
    airports: dict = None
    fetch_lock = asyncio.Lock()
    dep_api_url = 'https://www.airport.kr/dep/ap_ch/getDepPasSchList.do'
    arr_api_url = 'https://www.airport.kr/arr/ap_ch/getArrPasSchList.do'
    supported_airlines = []
    supported_airports = []

    def now_time(self):
        return get_now(get_offset_from_str(self.timezone))

    def extract_airport(self, data):
        if (ap := data.get("airportName1")) and len(ap) >= 0:
            return ap
        if (ap := data.get("airportName1En")) and len(ap) >= 0:
            return ap
        if (ap := data.get("p1code")) and len(ap) >= 0:
            return ap
        return '未知'

    async def parse_dep_flight_data_from_row(self, data: dict):
        code_share = data.get('codeshare')
        if code_share == 'Slave':
            return None
        dep_time = data.get('stime')
        act_dep_time = datetime.strptime(data.get("btime"), "%Y%m%d%H%M").strftime("%H:%M") + '(实)' if data.get(
            'btime') else None
        estimated_dep_time = data.get('etime')
        if not act_dep_time and estimated_dep_time:
            act_dep_time = estimated_dep_time + "(预)"

        via_airports = []
        for i in range(2, 4 + 1):
            _ap_name = data.get(f"airportName{i}")
            if not _ap_name or len(_ap_name) == 0:
                break
            via_airports.append(_ap_name)

        flight_date = datetime.strptime(data.get('sdate'), '%Y%m%d') if data.get('sdate') else None

        flight_info = FlightInfo(
            flight_no=data.get('masterflight'),
            shared_codes=[],
            airlines=data.get('airlineNameCh', data.get('flightCarrier')),
            airlines_code=data.get('flightCarrier'),
            arr_airport=self.extract_airport(data),
            arr_airport_code=data.get('p1code'),
            via_airports=via_airports,
            dep_airport=self.airport_name,
            dep_airport_code=self.airport_code,
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            date=flight_date,
            terminal=data.get('terminal'),
            gate=data.get('gatenumber'),
            status=data.get('stattxt'),
        )

        return flight_info

    async def parse_arr_flight_data_from_row(self, data: dict):
        code_share = data.get('codeshare')
        if code_share == 'Slave':
            return None
        arr_time = data.get('stime')
        act_arr_time = datetime.strptime(data.get("btime"), "%Y%m%d%H%M").strftime("%H:%M") + '(实)' if data.get(
            'btime') else None
        estimated_arr_time = data.get('etime')
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time + "(预)"

        via_airports = []
        for i in range(2, 4 + 1):
            _ap_name = data.get(f"airportName{i}")
            if not _ap_name or len(_ap_name) == 0:
                break
            via_airports.append(_ap_name)

        flight_date = datetime.strptime(data.get('sdate'), '%Y%m%d') if data.get('sdate') else None

        flight_info = FlightInfo(
            flight_no=data.get('masterflight'),
            shared_codes=[],
            airlines=data.get('airlineNameCh', data.get('flightCarrier')),
            airlines_code=data.get('flightCarrier'),
            arr_airport=self.airport_name,
            arr_airport_code=self.airport_code,
            via_airports=via_airports,
            dep_airport=self.extract_airport(data),
            dep_airport_code=data.get('p1code'),
            arr_time=arr_time,
            act_arr_time=act_arr_time,
            date=flight_date,
            carousel=data.get("carousel"),
            terminal=data.get('terminal'),
            status=data.get('stattxt'),
        )

        return flight_info

    def build_search_params(self, _form: QueryFlightForm, **kwargs):
        _now = self.now_time()
        today_date_str = _now.strftime("%Y%m%d")
        tomorrow_date_str = (_now + timedelta(days=1)).strftime("%Y%m%d")
        if terminal := kwargs.get("terminal", ""):
            terminal = terminal.upper()
        return {
            "intg": "",
            "keyWord": "",
            "curDate": today_date_str,
            "startTime": _now.replace(minute=0, second=0).strftime("%H%M"),
            "airPort": kwargs.get("airport"),
            "endTime": _now.replace(minute=59, second=0).strftime("%H%M"),
            "todayDate": today_date_str,
            "tomorrowDate": tomorrow_date_str,
            "todayTime": _now.strftime("%H:%M"),
            "curSTime": _now.replace(minute=0, second=0).strftime("%H%M"),
            "curETime": _now.replace(minute=59, second=0).strftime("%H%M"),
            "siteId": "ap_ch",
            "langSe": "zh",
            "scheduleListLength": "",
            "termId": terminal,
            "daySel": today_date_str,
            "fromTime": _now.replace(minute=0, second=0).strftime("%H%M"),
            "toTime": _now.replace(minute=59, second=0).strftime("%H%M"),
            "airport": _form.airport or "",
            "airline": kwargs.get("airline"),
            "airplane": _form.flight_no or ""
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
                _url = self.dep_api_url if is_dep else self.arr_api_url
                params = self.build_search_params(_form)
                logger.info(f'fetching url:{_url} {params}')
                resp = await client.post(_url, headers=headers, data=params)
                resp.raise_for_status()
                raw_flight_list = resp.json().get('scheduleList', [])
                _flights = await parse_flights(raw_flight_list)
                _flights = flight_filter(_flights, airlines_codes=_form.airlines_codes, airlines=_form.airlines,
                                         alliance=_form.alliance)
                flights.extend(_flights)

            flights = sorted(flights, key=lambda flight: flight.get_time(is_dep))
            flights = flights[0:max_result]
            return flights
        except Exception as e:
            logger.exception(e)
