import asyncio
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict

import httpx
from async_lru import alru_cache
from botpy import logging
from html2image import Html2Image
from jinja2 import Template
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from app.schemas.railsystem import TrainInfo
from app.utils.exceptions import BusinessException
from app.utils.http_utils import fetch
from app.utils.img_utils import image_to_base64, crop_bottom_blank
from app.utils.time_utils import describe_period, get_now

logger = logging.get_logger()


async def get_station_realtime(station_id: str, line_ids: List[str]) -> Dict[str, List[TrainInfo]] | None:
    async def _fetch(_url):
        r = await fetch(_url, 'post')
        if not r:
            return None
        return [TrainInfo(**x) for x in r if x]

    base_url = f'{os.getenv("REALTIME_API_BASEURL")}/realtime/train-info/station/v2/{station_id}/'
    tasks = []
    try:
        for line_id in line_ids:
            url = f'{base_url}{line_id}'
            task = asyncio.create_task(_fetch(url))
            task.line_id = line_id
            tasks.append(task)

        await asyncio.gather(*tasks)
        result = {task.line_id: task.result() for task in tasks if task}
        return result
    except Exception as e:
        logger.error(f'Get train info failed, station id:{station_id} line_ids:{line_ids}', exc_info=e)
        return None


async def get_schedule_image_by_browser(station_id: str, line_id: str,
                                        _date: datetime, **kwargs):
    filename = kwargs.get('filename')
    download_dir = kwargs.get('output_dir', "")
    if isinstance(download_dir, Path):
        download_dir = str(download_dir.absolute()).replace('\\', '/')
    target_file_path = os.path.join(download_dir, filename)

    chrome_options = Options()
    chrome_options.add_argument("--lang=zh-CN")
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    prefs = {
        "download.default_directory": download_dir,  # 设置下载目录
        "download.prompt_for_download": False,  # 禁止下载前的提示
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(360, 1080)
    url = f"{os.getenv("NEXT_TRAIN_PAGE_BASEURL")}/station/schedule/{station_id}/{line_id}"  # 修改为实际的网页 URL
    try:
        logger.info(f'Get url:{url}')
        driver.get(url)
        try:
            _ = WebDriverWait(driver, 30, poll_frequency=1).until(
                EC.presence_of_element_located((By.CLASS_NAME, "horizontal-item-wrapper"))
            )
            logger.info('页面加载完成')
        except TimeoutException:
            logger.error(f'等待时刻表页面加载超时 url: {url}')
            raise Exception(f"等待时刻表页面加载超时 预期url:{url}")
        download_button = driver.find_element(By.CLASS_NAME, "download-icon-wrapper")
        download_button.click()
        await asyncio.sleep(1)
        for i in range(15):
            if os.path.exists(target_file_path):
                return target_file_path
            else:
                await asyncio.sleep(1)
        raise Exception(f"下载时刻表超时 预期路径:{target_file_path}")
    except Exception as e:
        logger.error(f'Get schedule image failed url:{url}', exc_info=e)
        raise e
    finally:
        driver.quit()


@alru_cache(maxsize=16, ttl=3600)
async def get_line_by_id(line_id: str | int) -> dict:
    url = f'{os.getenv("REALTIME_BASEURL")}/file/railsystem/lines/id/{line_id}'
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


@alru_cache(maxsize=32, ttl=3600)
async def get_station_by_id(station_id: str | int) -> dict:
    url = f'{os.getenv("REALTIME_BASEURL")}/file/railsystem/stations/id/{station_id}'
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def process_schedule_data(schedule_data: dict, _line: dict):
    def gen_brief_name(name, _brief_name_map):
        if not name or len(name) == 0:
            return name

        _new_name = name[:1]
        suffixes = ['*', '#', '.', '**']

        for suffix in suffixes:
            if _new_name not in _brief_name_map:
                return _new_name
            _new_name += suffix
        return name

    def format_hour(_hour):
        if _hour < 24:
            return f"{_hour}时"
        _day_offset = _hour // 24
        _hour = _hour % 24

        if _day_offset == 1:
            return f"次日{_hour}时"

    def calc_style_class(train_info):
        classes = ['minute-wrapper']
        categories = train_info['categories']
        if 'EXPRESS' in categories:
            classes.append("express")
        elif 'NONSTOP' in categories:
            classes.append("express")
        elif 'THROUGH' in categories:
            classes.append("through")
        elif 'SHORT' in categories:
            classes.append("interval")

        if 'INITIAL' in categories:
            classes.append("initial")
        return ' '.join(classes)

    raw_schedule = schedule_data.get("schedules", [])
    cur_date = datetime.now()

    # 日期处理
    schedule_data["date"] = schedule_data.get("date")
    if schedule_data["date"] is None:
        schedule_data["date"] = cur_date.strftime("%Y-%m-%d")

    ID_INDEX = 0
    DEP_TIME_INDEX = 1
    TRAIN_CATEGORY_INDEX = 2
    short_terminal_station_ids = set()

    all_station_ids = set()
    for schedule in raw_schedule:
        all_station_ids.update(schedule.keys())
    line_terminal_station_ids = {_line["stations"][0]["id"], _line["stations"][-1]["id"]}
    for station_id in all_station_ids:
        if station_id not in line_terminal_station_ids:
            short_terminal_station_ids.add(station_id)

    # briefNameMap
    brief_name_map = {}
    for station_id in short_terminal_station_ids:
        station = schedule_data["stationMap"][station_id]
        station["briefName"] = gen_brief_name(station["name"], brief_name_map)
        brief_name_map[station_id] = station

    def convert_train_info(train_info):
        temp_train_info = {
            "id": train_info[ID_INDEX],
            "depTime": datetime(2024, 1, 1) + timedelta(seconds=train_info[DEP_TIME_INDEX]),
            "dayOffset": train_info[DEP_TIME_INDEX] // 86400,
            "categories": train_info[TRAIN_CATEGORY_INDEX]
        }
        return temp_train_info

    _schedules = []
    for schedule in raw_schedule:
        new_schedule = {}
        for entry in schedule:
            new_schedule[entry] = [convert_train_info(t) for t in schedule[entry]]
        _schedules.append(new_schedule)

    result = []
    for direction_schedule in _schedules:
        terminal_str = "/".join([
            schedule_data['stationMap'][k]['name']
            for k in direction_schedule
            if isinstance(schedule_data['stationMap'].get(k), dict)
        ])

        temp_schedules = []

        for station_id in direction_schedule:
            brief_name = brief_name_map.get(station_id, {}).get('briefName', None)
            t = []
            for it in direction_schedule[station_id]:
                is_first = 'INITIAL' in it['categories']

                dep_time = it['depTime']
                day_offset = it['dayOffset']

                if dep_time.second > 30:
                    dep_time += timedelta(minutes=1)
                    if dep_time.hour == 0 and dep_time.minute == 0:
                        day_offset += 1

                t.append({
                    'id': it['id'],
                    'briefName': brief_name,
                    'isFirst': is_first,
                    'depTime': dep_time,
                    'dayOffset': day_offset,
                    'showStr': str(dep_time.minute).zfill(2) + (brief_name or ""),
                    'style_classes': calc_style_class(it),
                })
            temp_schedules.extend(t)

        temp_schedules.sort(key=lambda x: x['depTime'])

        # 按小时分组（考虑 dayOffset）
        grouped = defaultdict(list)
        for item in temp_schedules:
            hour = item['depTime'].hour + item['dayOffset'] * 24
            grouped[hour].append(item)

        formatted_schedule = [{
            'hour': hour,
            'hourStr': format_hour(hour),  # 假设已有 format_hour 函数
            'dataList': data_list
        } for hour, data_list in grouped.items()]

        result.append({
            'terminal': terminal_str,
            'schedule': formatted_schedule
        })

    schedule_data["briefNameMap"] = brief_name_map
    schedule_data["schedules"] = result
    return schedule_data


def gen_station_schedule(schedule_header: dict, line: dict, station_name: str, _date: date, schedule_data: dict,
                         **kwargs) -> str:
    schedule_category_map = {
        'WORKDAY': '工作日时刻表',
        'WEEKEND': '周末时刻表',
        'HOLIDAY': '节假日时刻表',
    }
    category = schedule_category_map.get(schedule_header.get('category'), "")
    period = describe_period(schedule_header.get('period'))
    if category and period:
        version = category + '·' + period
    else:
        version = period
    brief_name_map = schedule_data["briefNameMap"]
    _data = {
        'schedule': {
            'date': _date.strftime('%Y-%m-%d'),
            'version': version,
            'effective_from_date': schedule_header.get('fromDate'),
            'briefNameList': list(brief_name_map.values()),
            'data': schedule_data['schedules'],
        },
        'station_name': station_name,
        'line_name': line.get('name'),
        'line_color': line.get('color'),
        'create_time': get_now(480).strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(Path('data/templates') / 'station-schedule-template.html', 'r', encoding='utf-8') as f:
        template_str = f.read()
        template = Template(template_str)
        html_str = template.render(**_data)
        hti = Html2Image(output_path=Path('data/temp'))
        hti.browser.flags = ['--no-sandbox', '--disable-dev-shm-usage', ]
        temp_filename = f'{uuid.uuid4()}.png'
        temp_file_path = hti.screenshot(html_str=html_str, save_as=temp_filename, size=(480, 2500))
        if not temp_file_path:
            raise BusinessException("生成时刻表图片失败")
        else:
            temp_file_path = temp_file_path[0]
        try:
            output_path = kwargs.get('output_dir')
            filename = kwargs.get('filename', f'{uuid.uuid4()}.png')
            if isinstance(output_path, Path):
                output_path = str(output_path.absolute())

            save_path = os.path.join(output_path, filename)
            crop_bottom_blank(image_path=temp_file_path, save_path=save_path)
            return save_path
        except Exception as e:
            raise e
        finally:
            os.remove(temp_file_path)


async def get_line_schedule_headers(line_id: str):
    async with httpx.AsyncClient() as client:
        url = f'{os.getenv("REALTIME_API_BASEURL")}/schedules/header/get/line/{line_id}'
        resp = await client.get(url)
        resp.raise_for_status()
        j_obj = resp.json()
        return j_obj['data']


async def get_schedule_image_by_html2image(station_id: str, line_id: str, _date: date = datetime.now(), **kwargs):
    line_task = asyncio.create_task(get_line_by_id(line_id))
    station_task = asyncio.create_task(get_station_by_id(station_id))

    schedule_headers = await get_line_schedule_headers(line_id)
    weekday = _date.weekday() + 1
    header = None
    for item in schedule_headers:
        if weekday in item['period']:
            header = item
    if not header:
        raise BusinessException(f"没有可用的时刻表 日期:{_date.strftime('%Y-%m-%d')} 线路ID:{line_id}")

    url = f'{os.getenv("REALTIME_API_BASEURL")}/realtime/train-info/station/schedule/v3/{station_id}/{header["scheduleId"]}'
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url)
            resp.raise_for_status()
            j_obj = resp.json()
            line = await line_task
            schedule_data = process_schedule_data(j_obj['data'], line)
    except Exception as e:
        logger.exception(f'获取时刻表原始数据失败,url:{url}', exc_info=e)
        raise BusinessException("获取时刻表数据失败")
    station = await station_task
    return gen_station_schedule(header, line=line, station_name=station.get("name"), _date=_date,
                                schedule_data=schedule_data, **kwargs)


async def get_schedule_image(station_name: str, line_name: str, station_id: str, line_id: str, _date: datetime,
                             **kwargs):
    filename = f'{station_name}-{line_name}_schedule.png'
    output_dir = Path(os.getenv('WORK_DIR')) / f'data/schedules/{_date.strftime("%Y-%m-%d")}'
    target_file_path = os.path.join(output_dir, filename)

    if os.path.exists(target_file_path):
        return target_file_path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if kwargs.get('use_browser'):
        return await get_schedule_image_by_browser(station_id, line_id, _date,
                                                   filename=filename, output_dir=output_dir, **kwargs)
    return await get_schedule_image_by_html2image(station_id, line_id, _date, filename=filename, output_dir=output_dir,
                                                  **kwargs)


async def get_train_plan(train_reg_no: str, _date: datetime):
    url = f'{os.getenv("REALTIME_API_BASEURL")}/metro-trace/get-train-plan/regno/'
    query_params = {
        'regNo': train_reg_no,
        'date': _date.strftime("%Y-%m-%d")
    }
    try:
        train_plan = await fetch(url, query_params=query_params, method='get')
    except Exception as e:
        logger.error(f'Get train plan failed, params:{query_params}', exc_info=e)
        raise Exception("")
