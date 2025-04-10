import asyncio
import os
import random
from datetime import datetime
from typing import List
from botpy import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from app.events.civil_aviation.Schemas import QueryFlightForm, FlightInfo

logger = logging.get_logger()


class ShanghaiFetcher:
    airport_name = '南京'
    timezone = 'Asia/Shanghai'
    hongqiao_code = 'SHA'
    pudong_code = 'PVG'

    def parse_dep_flight_data_from_row(self, tr):
        tds = tr.find_elements(By.TAG_NAME, "td")
        data = [td.text.strip() for td in tds]
        flight_date_str = data[0].strip()

        flight_codes = data[1].splitlines() if data[1] else []
        flight_no = flight_codes[0] if flight_codes else ""
        shared_codes = flight_codes[1:] if len(flight_codes) > 1 else []

        flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d')

        dep_time = data[6] if data[6] else None
        act_dep_time = data[8] + "(实)" if data[8] else None
        estimated_dep_time = data[7] if data[7] else None
        if not act_dep_time and estimated_dep_time:
            act_dep_time = estimated_dep_time + "(预)"

        flight_info = FlightInfo(
            flight_no=flight_no,
            shared_codes=shared_codes,
            airlines=data[2] if data[2] else None,
            aircraft_model=data[3] if data[3] else None,
            arr_airport=data[5],
            via_airports=[data[4]] if data[4] else [],
            dep_airport=self.airport_name,
            dep_time=dep_time,
            act_dep_time=act_dep_time,
            date=flight_date,
            terminal=data[9] if len(data) > 9 else None,
            gate=data[10] if len(data) > 10 else None,
            status=data[11] if len(data) > 11 else None,
        )

        return flight_info

    def parse_arr_flight_data_from_row(self, tr):
        tds = tr.find_elements(By.TAG_NAME, "td")
        data = [td.text.strip() for td in tds]
        flight_date_str = data[0].strip()
        flight_codes = data[1].splitlines() if data[1] else []
        flight_no = flight_codes[0] if flight_codes else ""
        shared_codes = flight_codes[1:] if len(flight_codes) > 1 else []

        flight_date = datetime.strptime(flight_date_str, '%Y-%m-%d')

        arr_time = data[6] if data[6] else None
        act_arr_time = data[8] if data[8] else None
        estimated_arr_time = data[7] if data[7] else None
        if not act_arr_time and estimated_arr_time:
            act_arr_time = estimated_arr_time + "(预)"

        flight_info = FlightInfo(
            flight_no=flight_no,
            airlines=data[2] if data[2] else None,
            aircraft_model=data[3] if data[3] else None,
            shared_codes=shared_codes,
            dep_airport=data[4],
            via_airports=[data[5]] if data[5] else [],
            arr_airport=self.airport_name,
            arr_time=arr_time,
            act_arr_time=act_arr_time,
            date=flight_date,
            terminal=data[9] if len(data) > 9 else None,
            carousel=data[10] if len(data) > 10 else None,
            status=data[11] if len(data) > 11 else None,
        )

        return flight_info

    async def fetch_flights(self, _form: QueryFlightForm, **kwargs):
        def filter_flights(__flights: List[FlightInfo]) -> List[FlightInfo]:
            _result: List[FlightInfo] = []
            target_aircraft_models = _form.aircraft_models
            if target_aircraft_models:
                for x in __flights:
                    if x.aircraft_model in target_aircraft_models:
                        _result.append(x)
            else:
                return __flights
            return _result

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
            use_query = False
            logger.info(f'loading url:{url}')
            driver.get(url)
            logger.info(f'page loaded, url:{url}')
            if kwargs.get('cargo', False):
                cargo_btn = driver.find_element(By.XPATH, "//div[@class='flightType']//a[text()='货班']")
                cargo_btn.click()
                await asyncio.sleep(5)
            if _form.flight_no:
                flight_no_input = driver.find_element(By.ID, "txtFlightNum")
                flight_no_input.send_keys(_form.flight_no)
                flight_btn = driver.find_element(By.ID, "btnSearchFlightNum")
                flight_btn.click()
                await asyncio.sleep(3)
            if _form.airlines:
                all_airlines_options = driver.find_elements(By.XPATH,
                                                            "//div[contains(text(),'航空公司')]/following-sibling::div[@class='drop-down']/dl/dd")
                airlines = [{'name': x.text, 'code': x.get_attribute('value')} for x in all_airlines_options]
                for index, option in enumerate(airlines):
                    if '不限' in option['name']:
                        continue
                    if _form.airlines in option['name'] or option['code'].upper() == _form.airlines.upper():
                        all_airlines_options[index].click()
                        use_query = True
                        break
            if _form.airport:
                all_airport_options = driver.find_elements(By.XPATH,
                                                           "//div[@id='airCities']/following-sibling::dl/dd")
                airports = [{'name': x.text, 'code': x.get_attribute('value')} for x in all_airport_options]
                for index, option in enumerate(airports):
                    if '不限' in option['name']:
                        continue
                    if _form.airport in option['name'] or option['code'].upper() == _form.airport.upper():
                        all_airport_options[index].click()
                        use_query = True
                        break

            if use_query:
                search_btn = driver.find_element(By.ID, "btnSearch")
                search_btn.click()
                await asyncio.sleep(3)

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
                data_table = driver.find_element(By.XPATH, "//div[@class='hangbanList']")
                rows = driver.find_elements(By.XPATH, "//table//tr")
                if len(rows) <= 1:
                    break
                # 排除表头
                rows = rows[1:]
                _flight = []
                if is_dep:
                    _flight = [self.parse_dep_flight_data_from_row(x) for x in rows]
                else:
                    _flight = [self.parse_arr_flight_data_from_row(x) for x in rows]
                print(f'page fetched, url:{driver.current_url}')
                flights.extend(filter_flights(_flight))
                if max_result and len(flights) >= max_result:
                    logger.info(f'arrive max result number, break.')
                    return flights[0:max_result]
                try:
                    next_page_btn = driver.find_element(By.XPATH, "//ul[@class='pagination']/li/a[text()='»']")
                    next_page_btn.click()
                except Exception as e:
                    print('no next page')
                    break

            return flights
        except Exception as e:
            logger.exception(e)
            _d = driver.get_screenshot_as_png()
            err_img_path = os.path.join(os.getenv('WORK_DIR'), 'data/temp',
                                        f"{self.airport_name}_fetcher_error_{datetime.now().strftime('%Y_%m_%d_%H%M%s')}.png")
            with open(err_img_path, "wb") as f:
                f.write(_d)
            raise e
        finally:
            driver.quit()
