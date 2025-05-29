import asyncio
import os
from uuid import uuid4

import httpx
from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from lxml import etree

from app.events.cma_weather.radar import get_radar_image
from app.events.common_events import wiki_search
from app.utils.html_utils import dom_to_image
from app.utils.message_utils import reply_image_message

logger = logging.get_logger()


async def handle_query_radar(message: GroupMessage | C2CMessage, station_name: str, **kwargs):
    img_url = await get_radar_image(station_name)
    _upload_media = await message._api.post_group_file(group_openid=message.group_openid, file_type=1,
                                                       url=img_url)
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=7,
        msg_id=message.id,
        media=_upload_media,
        msg_seq=2,
    )


async def handle_query_wiki_climate(message: GroupMessage | C2CMessage, city_name: str, **kwargs):
    url = await wiki_search(city_name)
    logger.info(f'handle_query_wiki_climate url: {url}')
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"},
                                    follow_redirects=True)
            resp.raise_for_status()
            tree = etree.HTML(resp.text)
            table_elements = tree.xpath("//table[contains(., '历史最高温') or contains(., 'Mean daily maximum')]")
            if not table_elements:
                await message.reply(content=f'未找到城市“{city_name}”的气候表格')
                return
            save_path = os.path.join(os.getenv("WORK_DIR"), f'data/temp/climate_{city_name}_{uuid4()}.png')
            try:
                dom_to_image(table_elements[0], save_path=save_path, size=(1000, 680), )
            except Exception as e:
                logger.error(e)
                await message.reply(content='生产气候图失败')
                return
            await reply_image_message(image_path=save_path, message=message, text=f'{city_name}气候')
        except Exception as e:
            logger.error(e)
            raise e
