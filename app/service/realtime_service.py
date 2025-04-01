import asyncio
import logging
import os
from typing import List, Dict

import httpx

from app.schemas.RailsystemSchemas import TrainInfo
from app.utils.http_utils import fetch

logger = logging.getLogger(__name__)


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
