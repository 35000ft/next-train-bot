import asyncio
import random
from datetime import datetime
from typing import List

import httpx
from botpy import logging
from lxml import etree

from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo
from app.events.civil_aviation.utils.filters import flight_filter
from app.events.civil_aviation.utils.util import estimate_page_by_time
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
    dep_flight_ratios = (0.02352, 0.270588, 0.2823529, 0.2823529, 0.1411764)
    arr_flight_ratios = (0.07335, 0.08557, 0.30318, 0.29339, 0.24449)

    # <div class="timetable_item clearfix">
    #   <div class="station fl">
    #       <p>CA715</p><p>SC131</p>
    #   </div>
    #   <div class="number fl">A320</div>
    #   <div class="company fl">中国国际航空</div>
    #   <div class="stop fl">曼谷</div>
    #   <div class="stop fl"></div>
    #   <div class="stop fl"></div>
    #   <div class="time fl">04-10 23:50</div>
    #   <div class="time fl"></div>
    #   <div class="time fl">04-11 00:11</div>
    #   <div class="import fl">463</div>
    #   <div class="end fr"><span>起飞</span></div>
    # </div>
    def parse_dep_flight_data_from_row(self, div):
        # Use relative XPath expression to select child div elements
        divs = div.xpath("./div")

        # Initialize a dictionary to store values keyed by a meaningful identifier.
        # This example assumes that each div has a class that uniquely identifies its role.
        data = {}
        for d in divs:
            # Get the class attribute to use as a key
            class_attr = d.get("class", "").strip()
            if class_attr:
                # Use the first class as the key (e.g., "station", "number", "company", "stop", etc.)
                key = class_attr.split()[0]
                # Extract text; using itertext() handles nested tags
                text = "".join(d.itertext()).strip()
                # If the key already exists and it is "stop", convert it into a list
                if key == "stop":
                    if len(text) > 0:
                        data.setdefault(key, []).append(text)
                elif key == 'station':
                    flight_nos = d.xpath("./p/text()")
                    if flight_nos:
                        data['flight_no'] = flight_nos[0]
                        data['shared_codes'] = flight_nos[1:]
                else:
                    data[key] = text
        stops = data.get("stop", [])
        if stops:
            arr_airport = stops[0]  # First stop as destination airport
            via_airports = stops[1:]  # Remaining stops as via airports (could be empty if not present)
        else:
            arr_airport = None
            via_airports = []

        # --------------------------
        times = div.xpath(".//div[contains(@class, 'time')]/text()")
        times = [t.strip() for t in times if t.strip()]

        # Scheduled departure time: Parse to get flight_date and departure time.
        dep_time_raw = times[0] if times else ""
        flight_date: datetime
        dep_time = None
        if dep_time_raw:
            parts = dep_time_raw.split()
            if len(parts) == 2:
                flight_date_str, dep_time = parts
                flight_date = datetime.fromisoformat(f'{datetime.now().year}-{flight_date_str.strip()}')
            else:
                # If format is unexpected, assign the full string to dep_time (or handle error)
                dep_time = dep_time_raw

        # Actual departure time: Also extract only the hh:mm part if available.
        act_dep_time = None
        if len(times) > 1 and times[1]:
            act_parts = times[1].split()
            if len(act_parts) == 2:
                # For actual departure time we keep only the time part.
                act_dep_time = act_parts[1]
            else:
                act_dep_time = times[1]

        flight_info = FlightInfo(
            flight_no=data.get("flight_no"),
            shared_codes=data.get("shared_codes", []),
            airlines=data.get("company"),
            aircraft_model=data.get("number"),
            arr_airport=arr_airport,
            via_airports=via_airports,
            dep_airport=self.airport_name,
            dep_airport_code=self.airport_code,
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            date=flight_date,  # flight_date derived from departure time string
            gate=data.get("import"),
            status=data.get("end")  # Adjust based on how status is represented in your HTML
        )

        return flight_info

    def parse_arr_flight_data_from_row(self, div):
        # Use relative XPath expression to select child div elements.
        divs = div.xpath("./div")

        # Initialize a dictionary to store values keyed by a meaningful identifier.
        data = {}
        for d in divs:
            class_attr = d.get("class", "").strip()
            if class_attr:
                key = class_attr.split()[0]
                text = "".join(d.itertext()).strip()

                if key == "stop":
                    if len(text) > 0:
                        data.setdefault(key, []).append(text)
                elif key == 'station':
                    flight_nos = d.xpath("./p/text()")
                    if flight_nos:
                        data['flight_no'] = flight_nos[0]
                        data['shared_codes'] = flight_nos[1:]
                else:
                    # For keys like "stop" in arrival we typically don't need a list; use text directly.
                    data[key] = text

        stops = data.get("stop", [])
        if stops:
            dep_airport = stops[0]  # First stop as destination airport
            via_airports = stops[1:]  # Remaining stops as via airports (could be empty if not present)
        else:
            dep_airport = '未知'
            via_airports = []

        # 计划到达时间 变更到达时间 实际到达时间
        times = div.xpath(".//div[contains(@class, 'time')]/text()")
        times = [t.strip() for t in times if t.strip()]

        arr_time_raw = times[0] if times else ""
        flight_date = None
        arr_time = None
        if arr_time_raw:
            parts = arr_time_raw.split()
            if len(parts) == 2:
                flight_date_str, arr_time = parts
                # Construct flight_date using the current year and the MM-DD from flight_date_str.
                try:
                    flight_date = datetime.fromisoformat(f'{datetime.now().year}-{flight_date_str.strip()}')
                except Exception as e:
                    # Handle parsing error if any, e.g., by logging or setting flight_date to None.
                    flight_date = None
            else:
                arr_time = arr_time_raw

        # Extract the actual arrival time, if available.
        act_arr_time = None
        if len(times) > 2 and times[2]:
            act_parts = times[2].split()
            act_arr_time = act_parts[1] + '(实)'
        if not act_arr_time and len(times) > 1 and times[1]:
            act_parts = times[1].split()
            act_arr_time = act_parts[1] + '(预)'

        flight_info = FlightInfo(
            flight_no=data.get("flight_no"),
            shared_codes=data.get("shared_codes", []),
            airlines=data.get("company"),
            aircraft_model=data.get("number"),
            dep_airport=dep_airport,
            arr_airport=self.airport_name,
            arr_airport_code=self.airport_code,
            via_airports=via_airports,
            arr_time=arr_time,
            act_arr_time=act_arr_time,
            date=flight_date,
        )
        return flight_info

    def parse_page(self, _html_string: str, is_dep: bool) -> List[FlightInfo]:
        tree = etree.HTML(_html_string)
        rows = tree.xpath("//div[contains(@class,'timetable_item')]")
        if is_dep:
            flights = [self.parse_dep_flight_data_from_row(x) for x in rows]
        else:
            flights = [self.parse_arr_flight_data_from_row(x) for x in rows]
        return flights

    def estimate_page(self, _time: datetime, max_page: int, is_dep: bool) -> int:
        # todo day_offset
        _ratios = self.dep_flight_ratios if is_dep else self.arr_flight_ratios
        return estimate_page_by_time(_time, max_page=max_page, ratios=_ratios, day_offset=0)

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
        # todo
        def filter_flights(__flights: List[FlightInfo]) -> List[FlightInfo]:
            return flight_filter(__flights, aircraft_models=_form.aircraft_models)

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

            target_time: datetime = _form.at_time or get_now(480)
            cur_page = self.estimate_page(target_time, max_page, is_dep)
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
                            _flights = self.parse_page(_resp.text, is_dep)
                    else:
                        _flights = self.parse_page(resp.text, is_dep)

                    if _flights:
                        # 该页最后一个航班的时间如果在目标时间之前则从该页下一页开始查起
                        last_flight = max(_flights, key=lambda flight: flight.get_time(is_dep))
                        if cur_page < max_page and not last_flight.is_after(target_time, is_dep):
                            fetch_count = 0
                            cur_page = cur_page + 1
                            continue

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
