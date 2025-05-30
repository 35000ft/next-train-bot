import os
import re
from uuid import uuid4

from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from lxml import etree
from wikipedia import wikipedia, PageError

from app.events.cma_weather.radar import get_radar_image
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
    try:
        city_name = city_name.strip('"“”')
        pattern = r'^(?=.*[A-Za-z])[A-Za-z0-9_ ]+$'
        if not kwargs.get('l') and re.match(pattern, city_name):
            kwargs['l'] = 'en'
        lang = kwargs.get('l', 'zh')
        wikipedia.set_lang(lang)

        try:
            page = wikipedia.page(city_name)
        except PageError as e:
            search_result_words = wikipedia.search(city_name)
            if search_result_words:
                page = wikipedia.page(search_result_words[0])
            else:
                await message.reply(content=f'没有找到任何关于"{city_name}"的内容 使用语言:{lang}')
                return
        tree = etree.HTML(page.html())
        table_elements = tree.xpath(
            "//table[contains(., '日均气温') or contains(., 'Climate data for')]")
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
