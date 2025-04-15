import asyncio
import os
import random
from datetime import datetime
from typing import List, Optional

from botpy import logging
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo
from app.events.civil_aviation.utils.filters import flight_filter
from app.utils.time_utils import get_now

logger = logging.get_logger()


class ShanghaiFetcher:
    timezone = 'Asia/Shanghai'

    def self_airport_name(self):
        pass

    def self_airport_code(self):
        pass

    def is_self_airport(self, airport: str):
        pass

    # 0 <td>06:45</td>
    # 1 <td>CA8535<br><div>
    #   <div class="HangBan_list"><div class="List">
    #   <marquee class="marquee" direction="left" scrollamount="3" onmouseover="this.stop()" onmouseout="this.start()">
    #   <ul><li>NZ3729</li><li>ZH4821</li>
    #   </ul></marquee></div></div></div>
    # </td>
    # 2 <td>中国国际航空公司</td>
    # 3 <td>浦东(T2)</td>
    # 4 <td style="display: none;">兰州<br></td>
    # 5 <td>K</td>
    # 6 <td style="display: none;">实际出发07:07</td>
    # 7 <td><a href="/flights/info.html?flightno=CA8535&amp;time=06:45&amp;date=2025-04-10" target="_blank">查看</a></td>

    def parse_dep_flight_data_from_row(self, tr, flight_date: datetime):
        tds = tr.find_elements(By.TAG_NAME, "td")
        data = [td.text.strip() for td in tds]
        dep_airport_name = data[3]
        if not self.is_self_airport(dep_airport_name):
            return None
        flight_no = data[1].split('\n')[0] if data[1] else None

        dep_time = data[0]
        act_dep_time = data[6] if '实际' in data[6] else None
        estimated_dep_time = data[6] if '预计' in data[6] else None
        if not act_dep_time and estimated_dep_time:
            act_dep_time = estimated_dep_time

        flight_info = FlightInfo(
            flight_no=flight_no,
            shared_codes=[],
            airlines=data[2] if data[2] else None,
            arr_airport=data[4],
            via_airports=[],
            dep_airport=self.self_airport_name(),
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            date=flight_date,
            terminal=data[3].replace('浦东', '').replace('虹桥', '').strip('()'),
            status=data[6],
        )

        return flight_info

    def parse_arr_flight_data_from_row(self, tr, flight_date: datetime):
        tds = tr.find_elements(By.TAG_NAME, "td")
        data = [td.text.strip() for td in tds]
        dep_airport_name = data[3]
        if not self.is_self_airport(dep_airport_name):
            return None
        flight_no = data[1].split('\n')[0] if data[1] else None

        arr_time = data[0]
        act_arr_time = data[6] if '实际' in data[6] else None
        estimated_arr_time = data[6] if '预计' in data[6] else None
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time

        flight_info = FlightInfo(
            flight_no=flight_no,
            shared_codes=[],
            airlines=data[2] if data[2] else None,
            arr_airport=self.self_airport_name(),
            via_airports=[],
            dep_airport=data[5] if data[5] else None,
            dep_time=arr_time,
            act_dep_time=act_arr_time,
            date=flight_date,
            terminal=data[3].replace('浦东', '').replace('虹桥', '').strip('()'),
            status=data[6],
        )

        return flight_info

    def calc_direction(self, is_dep: bool, is_international: bool = False):
        if is_dep:
            if is_international:
                return '3'
            else:
                return '1'
        else:
            if is_international:
                return '4'
            else:
                return '2'

    def parse_flight_from_jsobj(self, js_obj: dict, is_dep: bool) -> Optional[FlightInfo]:
        def format_flight_time(time_str) -> str:
            return time_str.split(' ')[-1][0:5]

        if is_dep:
            if not self.is_self_airport(js_obj['出发地']):
                return None
            return FlightInfo(
                flight_no=js_obj['主航班号'],
                shared_codes=[],
                airlines=js_obj['航空公司'],
                arr_airport=js_obj['目的地'].replace(' ', '') if js_obj.get('目的地') else '--',
                arr_airport_code=js_obj.get('目的地代号'),
                via_airports=[],
                dep_airport=self.self_airport_name(),
                dep_airport_code=self.self_airport_code(),
                dep_time=format_flight_time(js_obj.get('计划出发时间')),
                act_dep_time=format_flight_time(js_obj.get('实际出发时间')),
                arr_time=format_flight_time(js_obj.get('计划到达时间')),
                act_arr_time=format_flight_time(js_obj.get('预计到达时间')) if js_obj.get('预计到达时间') else None,
                date=datetime.fromisoformat(js_obj['时间显示']),
                terminal=js_obj['候机楼'].replace('浦东', '').replace('虹桥', '').strip('()'),
                status=js_obj['状态'],
            )
        else:
            if not self.is_self_airport(js_obj['目的地']):
                return None
            return FlightInfo(
                flight_no=js_obj['主航班号'],
                shared_codes=[],
                airlines=js_obj['航空公司'],
                arr_airport=self.self_airport_name(),
                arr_airport_code=self.self_airport_name(),
                via_airports=[],
                dep_airport=js_obj['出发地'].replace(' ', '') if js_obj.get('出发地') else '--',
                dep_airport_code=js_obj.get('出发地代号'),
                dep_time=format_flight_time(js_obj.get('计划出发时间')),
                act_dep_time=format_flight_time(js_obj.get('实际出发时间')),
                arr_time=format_flight_time(js_obj.get('计划到达时间')),
                act_arr_time=format_flight_time(js_obj.get('预计到达时间')) if js_obj.get('预计到达时间') else None,
                date=datetime.fromisoformat(js_obj['时间显示']),
                terminal=js_obj['候机楼'].replace('浦东', '').replace('虹桥', '').strip('()'),
                status=js_obj['状态'],
                carousel=js_obj.get('行李传送带'),
            )

    async def fetch_flights(self, _form: QueryFlightForm, **kwargs):
        def filter_flights(__flights: List[FlightInfo]) -> List[FlightInfo]:
            return flight_filter(flights, flight_no=_form.flight_no, airlines=_form.airlines,
                                 airlines_codes=_form.airlines_codes)

        is_dep = True if not kwargs.get('arr') else False
        url: str = 'https://www.shairport.com/flights/index.html'
        chrome_options = Options()
        chrome_options.add_argument("--lang=zh-CN")
        if kwargs.get('headless', True):
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")

        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        flights = []
        try:
            logger.info(f'loading url:{url}')
            driver.get(url)
            logger.info(f'page loaded, url:{url}')
            if kwargs.get('cargo', False):
                cargo_btn = driver.find_element(By.XPATH, "//div[@class='flightType']//a[text()='货班']")
                cargo_btn.click()
                await asyncio.sleep(5)
            if _form.airlines:
                all_airlines_options = driver.find_elements(By.XPATH,
                                                            "//div[contains(text(),'航空公司')]/following-sibling::div[@class='drop-down']/dl/dd")
                airlines = [{'name': x.text, 'code': x.get_attribute('value')} for x in all_airlines_options]
                for index, option in enumerate(airlines):
                    if '不限' in option['name']:
                        continue
                    if _form.airlines in option['name'] or option['code'].upper() == _form.airlines.upper():
                        all_airlines_options[index].click()
                        break
            if _form.airport:
                all_airport_options = driver.find_elements(By.XPATH,
                                                           "//div[@id='airCities']/following-sibling::dl/dd")
                airports = [{'name': x.get_attribute('innerText').replace(' ', ''), 'code': x.get_attribute('value')}
                            for x in all_airport_options]
                for index, option in enumerate(airports):
                    if '不限' in option['name']:
                        continue
                    if _form.airport in option['name'] or option['code'].upper() == _form.airport.upper():
                        ap_option = all_airport_options[index]
                        selector = ap_option.find_element(By.XPATH, '../..')
                        actions = ActionChains(driver)
                        actions.move_to_element(selector).perform()
                        await asyncio.sleep(0.5)
                        ap_option.click()
                        break
            # 设置 国内出发/到达 国际出发/到达
            driver.execute_script(f"this.app.direction='{self.calc_direction(is_dep, kwargs.get('int', False))}'")
            now = get_now(480)
            # 时间范围 默认从现在开始
            driver.execute_script(f"document.getElementById('TimeMinute').value='{now.strftime('%H:%M')}'")

            search_btn = driver.find_element(By.ID, "btnSearch")
            search_btn.click()
            await asyncio.sleep(1)
            while True:
                if driver.execute_script(
                        "return window.performance.getEntriesByType('resource').filter(r => !r.responseEnd).length") == 0:
                    break
                await asyncio.sleep(1)

            if from_page := kwargs.get('from_page'):
                try:
                    page_li = driver.find_element(By.XPATH, f"//ul[@class='el-pager']/li[text()='{from_page}']")
                    page_li.click()
                    await asyncio.sleep(5)
                except Exception as e:
                    raise ValueError(f"没有页码:{from_page}")

            max_result = kwargs.get('max_result', 20)

            max_fetch_page = kwargs.get('max_fetch_page', 3)
            fetch_count = 0
            while True:
                if fetch_count >= max_fetch_page:
                    break
                else:
                    fetch_count += 1
                await asyncio.sleep(random.uniform(1.0, 2.0))
                _flight = []
                flight_list = driver.execute_script("return this.app.flightList;")
                _flight = [self.parse_flight_from_jsobj(x, is_dep) for x in flight_list]
                logger.info(f'page fetched')
                flights.extend(filter_flights(_flight))
                if max_result and len(flights) >= max_result:
                    logger.info(f'arrive max result number, break.')
                    return flights[0:max_result]
                try:
                    next_page_btn = driver.find_element(By.XPATH, "//button[@class='btn-next']")
                    next_page_btn.click()
                except Exception as e:
                    logger.warn('no next page')
                    break

            return flights
        except Exception as e:
            logger.exception(e)
            _d = driver.get_screenshot_as_png()
            err_img_path = os.path.join(os.getenv('WORK_DIR'), 'data/temp',
                                        f"{self.self_airport_name()}_fetcher_error_{datetime.now().strftime('%Y_%m_%d_%H%M%s')}.png")
            with open(err_img_path, "wb") as f:
                f.write(_d)
            raise e
        finally:
            driver.quit()


class PVGFetcher(ShanghaiFetcher):
    airport_name = '上海浦东'
    airport_code = 'PVG'

    def is_self_airport(self, airport: str):
        return '浦东' in airport or 'PVG' == airport.upper()

    def self_airport_name(self):
        return self.airport_name

    def self_airport_code(self):
        return self.airport_code


class SHAFetcher(ShanghaiFetcher):
    airport_name = '上海虹桥'
    airport_code = 'SHA'

    def is_self_airport(self, airport: str):
        return '虹桥' in airport or 'SHA' == airport.upper()

    def self_airport_name(self):
        return self.airport_name

    def self_airport_code(self):
        return self.airport_code
