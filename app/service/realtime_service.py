import asyncio
import os
import sys
from datetime import datetime
from typing import List, Dict

from botpy import logging
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from app.schemas.RailsystemSchemas import TrainInfo
from app.utils.http_utils import fetch
from app.utils.img_utils import image_to_base64

logger = logging.get_logger()


async def get_station_realtime(station_id: str, line_ids: List[str]) -> Dict[str, List[TrainInfo]] | None:
    async def _fetch(_url):
        r = await fetch(_url, 'post')
        if not r:
            return None
        return [TrainInfo(**x) for x in r if x]

    base_url = f'https://nmtr.online/metro-realtime/station/train-info/v2/{station_id}/'
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


async def get_schedule_image(station_name: str, line_name: str, station_id: str, line_id: str, _date: datetime):
    filename = f'{station_name}-{line_name}_schedule.png'
    download_dir = os.path.join(os.getenv('WORK_DIR'), f'data/schedules/{_date.strftime("%Y-%m-%d")}')
    if 'win' in sys.platform.lower():
        download_dir = download_dir.replace('/', '\\')
    target_file_path = os.path.join(download_dir, filename)

    if os.path.exists(target_file_path):
        return image_to_base64(target_file_path)
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

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
    url = f"https://nmtr.online/next-train/#/station/schedule/{station_id}/{line_id}"  # 修改为实际的网页 URL
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
                return image_to_base64(target_file_path)
            else:
                await asyncio.sleep(1)
        raise Exception(f"下载时刻表超时 预期路径:{target_file_path}")
    except Exception as e:
        logger.error(f'Get schedule image failed url:{url}', exc_info=e)
        raise e
    finally:
        driver.quit()


async def main():
    x = await get_schedule_image('新街口', '2号线', '13', '2', datetime.now())
    print(x)
