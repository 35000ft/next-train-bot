import asyncio
import os
import random
import urllib.parse
from datetime import datetime
from typing import List, Optional

import httpx
from botpy import logging
from lxml import etree
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


class HGHFetcher:
    airport_name = '杭州'
    airport_code = 'HGH'
    timezone = 'Asia/Shanghai'
    airports: dict = None
    fetch_lock = asyncio.Lock()
    baseurl = 'https://www.hzairport.com'

    def parse_dep_flight_data_from_row(self, data: dict, flight_date: datetime):
        flights = data['flight']
        main_flight = flights[0]

        flight_no = main_flight['no'].replace(' ', '').strip()
        airlines = main_flight['airline']
        shared_codes = [x['no'].replace(' ', '') for x in flights[1:]] if len(flights) > 1 else []

        dep_time = data['time'] if data['time'] else None
        act_dep_time = data['status'].replace("启航", "").strip() + "(实)" if '启航' in data['status'] else None
        estimated_dep_time = data['status'].replace("预计", "").strip() if '预计' in data['status'] else None
        if not act_dep_time and estimated_dep_time:
            act_dep_time = estimated_dep_time + "(预)"

        flight_info = FlightInfo(
            flight_no=flight_no,
            shared_codes=shared_codes,
            airlines=airlines,
            aircraft_model='--',
            arr_airport='airport',
            arr_airport_code='airport_code',
            via_airports=[],
            dep_airport=self.airport_name,
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            date=flight_date,
            terminal=data['terminal'] if data.get('terminal') else None,
            gate=data['gate'] if data.get('gate') else None,
            status=data['status'] if data.get('status') else None,
        )

        return flight_info

    def parse_arr_flight_data_from_row(self, data: dict, flight_date: datetime):
        flights = data['flight']
        main_flight = flights[0]

        flight_no = main_flight['no'].replace(' ', '').strip()
        airlines = main_flight['airline']
        shared_codes = [x['no'].replace(' ', '') for x in flights[1:]] if len(flights) > 1 else []

        arr_time = data['time'] if data['time'] else None
        act_arr_time = data['status'] if '到闸口' in data['status'] else None
        estimated_arr_time = data['status'].replace("预计", "").strip() if '预计' in data['status'] else None
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time + "(预)"

        flight_info = FlightInfo(
            flight_no=flight_no,
            shared_codes=shared_codes,
            airlines=airlines,
            aircraft_model='--',
            dep_airport='airport',
            dep_airport_code='airport_code',
            via_airports=[],
            arr_airport=self.airport_name,
            arr_time=arr_time,
            act_arr_time=act_arr_time,
            date=flight_date,
            terminal=data['terminal'] if data.get('terminal') else None,
            carousel=data['baggage'] if data.get('baggage') else None,
            status=data['status'] if data.get('status') else None,
            stand=data['stand'] if data.get('stand') else None,
        )

        return flight_info

    # TODO
    def parse_page(self, _html_string: str) -> List[FlightInfo]:
        tree = etree.HTML(_html_string)
        rows = tree.xpath("//div[contains(@class,'timetable_item')]")
        return []

    def estimate_page(self, _time: datetime, max_page: int) -> int:
        # 当前小时分钟秒转为“从今天4:00开始的分钟数”
        total_minutes_per_day = 24 * 60
        minutes_per_page = total_minutes_per_day / max_page

        # 当前时间的分钟数（从0点起）
        current_minutes = _time.hour * 60 + _time.minute + _time.second / 60

        # 从4:00起的分钟数（小于4:00的当作加上24小时）
        minutes_since_4am = current_minutes - 4 * 60
        if minutes_since_4am < 0:
            minutes_since_4am += total_minutes_per_day

        # 计算页码
        page = int(minutes_since_4am / minutes_per_page) + 1
        page = min(max(page, 1), max_page)
        if page > 1:
            return page - 1
        return page

    def build_page_url(self, _params: dict, page: int, is_dep: bool) -> str:
        base_uri = '/flight/index/' if is_dep else '/flight/arrive/'
        parts = [self.baseurl, base_uri]
        if _params.get('city'):
            parts.append('city/' + _params.get('city'))
        if _params.get('identity'):
            parts.append('identity/' + _params.get('identity'))
        if _params.get('airline'):
            parts.append('airline/' + _params.get('airline'))
        parts.append(f'p/{page}')
        return ''.join(parts)

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

        is_dep = True if not kwargs.get('arr') else False
        first_url: str = 'https://www.hzairport.com/flight/index.html' if is_dep \
            else 'https://www.hzairport.com/flight/arrive.html'

        flights = []
        params = {
            'city': None,
            'identity': None,
            'airline': None,
        }
        # 第一页响应
        async with httpx.AsyncClient() as client:
            logger.info(f'loading url:{first_url} params:{params}')
            resp = await client.post(first_url, data=params)
            resp.raise_for_status()
            page_tree = etree.HTML(resp.text)
        try:
            if _form.flight_no:
                params['identity'] = _form.flight_no
            if _form.airlines:
                all_airlines_options = page_tree.xpath("//div[@class='flight_select fl']//li")
                airlines = [{'name': x.text, 'code': x.get_attribute('data-id')} for x in all_airlines_options]
                for option in airlines:
                    if _form.airlines in option['name'] or option['code'].upper() == _form.airlines.upper():
                        params['airline'] = option['name']
                        break
            if _form.airport:
                params['airport'] = _form.airport

            max_result = kwargs.get('max_result', 20)
            page_nums = page_tree.xpath("//div[@class='page_con clearfix']//a[@class='num']/text()")
            if len(page_nums) <= 2:
                max_page = 1
            else:
                max_page: int = int(page_nums[-2].strip('..').strip())

            now = get_now(480)
            cur_page = self.estimate_page(now, max_page)
            logger.info(f'curpage:{cur_page}')
            max_fetch_page = kwargs.get('max_fetch_page', 3)
            fetch_count = 0
            while True:
                _url = first_url
                try:
                    if fetch_count >= max_fetch_page:
                        break
                    else:
                        fetch_count += 1
                    if cur_page != 1:
                        _url = self.build_page_url(params, cur_page, is_dep)
                        logger.info(f'getting page:{_url}')
                        async with httpx.AsyncClient() as client:
                            _resp = await client.get(_url)
                            _resp.raise_for_status()
                            _flights = self.parse_page(_resp.text)
                    else:
                        _flights = self.parse_page(resp.text)

                    flights.extend(filter_flights(_flights))
                    if len(flights) >= max_result:
                        return flights[:max_result]
                    if cur_page < max_page:
                        cur_page += 1
                    else:
                        break
                    
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    logger.exception(e)
                    logger.info(f'Get page error:{_url}')

            return flights
        except Exception as e:
            logger.exception(e)
