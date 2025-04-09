import asyncio
import os
import random
from datetime import datetime
from typing import List, Optional

import httpx
from botpy import logging
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo
from app.utils.time_utils import get_now

logger = logging.get_logger()

headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}


class Airport(BaseModel):
    country: str
    code: str
    description: str


class HKGFetcher:
    airport_name = '香港'
    airport_code = 'HKG'
    timezone = 'Asia/Shanghai'
    airports: dict = None
    fetch_lock = asyncio.Lock()

    async def parse_airport(self, iata_code: str) -> Optional[Airport]:
        if self.airports:
            return self.airports.get(iata_code)
        async with self.fetch_lock:
            async with httpx.AsyncClient() as client:
                url = 'https://www.hongkongairport.com/flightinfo-rest/rest/airports'
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                airports = [Airport(code=x['code'], description=x['description'][1], country=x.get('country')) for x in
                            data
                            if x['description'] and x['code']]
                self.airports = {x.code: x for x in airports}
                return self.airports.get(iata_code)

    # {
    #     "time": "00:05",
    #     "flight": [
    #         {
    #             "no": "CX 143",
    #             "airline": "CPA"
    #         }
    #     ],
    #     "status": "启航 00:20",
    #     "statusCode": null,
    #     "destination": [
    #         "PER"
    #     ],
    #     "terminal": "T1",
    #     "aisle": "A",
    #     "gate": "61"
    # }

    async def parse_dep_flight_data_from_row(self, data: dict, flight_date: datetime):
        flights = data['flight']
        main_flight = flights[0]

        flight_no = main_flight['no'].replace(' ', '').strip()
        airlines = main_flight['airline']
        shared_codes = [x['no'].replace(' ', '') for x in flights[1:]] if len(flights) > 1 else []

        destination: List[Airport] = [await self.parse_airport(code) for code in data['destination']]
        airport = ' / '.join([x.description for x in destination if x])
        airport_code = destination[-1].code

        dep_time = data['time'] if data['time'] else None
        act_dep_time = data['status'].replace("启航", "").strip() + "(实)" if '启航' in data['status'] else None
        estimated_dep_time = data['status'].replace("预计", "").strip() + "(预)" if '预计' in data['status'] else None
        if not act_dep_time and estimated_dep_time:
            act_dep_time = estimated_dep_time + "(预)"

        flight_info = FlightInfo(
            flight_no=flight_no,
            shared_codes=shared_codes,
            airlines=airlines,
            aircraft_model='--',
            arr_airport=airport,
            arr_airport_code=airport_code,
            via_airports=[],
            dep_airport=self.airport_name,
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            date=flight_date,
            terminal=data['terminal'] if data['terminal'] else None,
            gate=data['gate'] if data['gate'] else None,
            status=data['status'] if data['status'] else None,
        )

        return flight_info

    async def parse_arr_flight_data_from_row(self, data: dict, flight_date: datetime):
        flights = data['flight']
        main_flight = flights[0]

        flight_no = main_flight['no'].replace(' ', '').strip()
        airlines = main_flight['airline']
        shared_codes = [x['no'].replace(' ', '') for x in flights[1:]] if len(flights) > 1 else []

        destination: List[Airport] = [await self.parse_airport(code) for code in data['origin']]
        airport = ' / '.join([x.description for x in destination if x])
        airport_code = destination[-1].code

        arr_time = data['time'] if data['time'] else None
        act_arr_time = data['status'] if '到闸口' in data['status'] else None
        estimated_arr_time = data['status'].replace("预计", "").strip() + "(预)" if '预计' in data['status'] else None
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time + "(预)"

        flight_info = FlightInfo(
            flight_no=flight_no,
            shared_codes=shared_codes,
            airlines=airlines,
            aircraft_model='--',
            dep_airport=airport,
            dep_airport_code=airport_code,
            via_airports=[],
            arr_airport=self.airport_name,
            arr_time=arr_time,
            act_arr_time=act_arr_time,
            date=flight_date,
            terminal=data['terminal'] if data['terminal'] else None,
            carousel=data['baggage'] if data['baggage'] else None,
            status=data['status'] if data['status'] else None,
            stand=data['stand'] if data['stand'] else None,
        )

        return flight_info

    async def fetch_flights(self, _form: QueryFlightForm, **kwargs):
        def filter_flights(__flights: List[FlightInfo]) -> List[FlightInfo]:
            _result: List[FlightInfo] = __flights
            if target_airport := _form.airport:
                if is_dep:
                    _result = filter(
                        lambda x: target_airport in x.arr_airport or (
                                x.arr_airport_code and target_airport.upper() == x.arr_airport_code),
                        list(_result))
                else:
                    _result = filter(
                        lambda x: target_airport in x.dep_airport or (
                                x.dep_airport_code and target_airport.upper() == x.dep_airport_code),
                        list(_result))
            if _form.flight_no:
                _result = filter(lambda x: _form.flight_no in x.flight_no if x.flight_no else False, list(_result))
            if _form.airlines:
                _result = filter(lambda x: _form.airlines in x.airlines if x.flight_no else False, list(_result))

            if _form.at_time:
                _result = filter(lambda x: x.is_after(_form.at_time, is_dep), list(_result))
            else:
                _result = filter(lambda x: x.is_after(now, is_dep), list(_result))
            return list(_result)

        api_url = 'https://www.hongkongairport.com/flightinfo-rest/rest/flights'
        now = get_now(480)
        is_dep = True if not kwargs.get('arr') else False
        params = {
            'span': 1,
            'date': now.strftime('%Y-%m-%d'),
            'lang': 'zh_CN',
            'cargo': kwargs.get('cargo', False),
            'arrival': not is_dep,
        }

        flights: List[FlightInfo] = []
        try:
            logger.info(f'fetching url:{api_url}')
            async with httpx.AsyncClient() as client:
                resp = await client.get(api_url, headers=headers, params=params)
                resp.raise_for_status()
                j_obj = resp.json()
                for date_data in j_obj:
                    _date: datetime = datetime.strptime(date_data['date'], '%Y-%m-%d')
                    _list = date_data['list']
                    if is_dep:
                        flights.extend([await self.parse_dep_flight_data_from_row(x, _date) for x in _list])
                    else:
                        flights.extend([await self.parse_arr_flight_data_from_row(x, _date) for x in _list])

                flights = filter_flights(flights)
                max_result = kwargs.get('max_result', 20)
                flights = flights[0:max_result]
                flights_sorted = sorted(flights, key=lambda flight: flight.get_time(is_dep))
                return flights_sorted
        except Exception as e:
            logger.exception(e)
