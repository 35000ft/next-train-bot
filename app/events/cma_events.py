import os
import re
from uuid import uuid4

from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from lxml import etree
from wikipedia import wikipedia, PageError, DisambiguationError

from app.events.cma_weather.radar import get_radar_image
from app.utils.command_utils import save_context_command
from app.utils.common import command_wrapper
from app.utils.exceptions import BusinessException
from app.utils.html_utils import dom_to_image
from app.utils.message_utils import reply_image_message
from app.utils.qqbot_utils import get_group_and_user_id
from app.utils.wechat_utils import upload_media

logger = logging.get_logger()


@command_wrapper(help='雷达南京')
async def handle_query_radar(message: GroupMessage | C2CMessage, station_name: str, **kwargs):
    try:
        img_url = await get_radar_image(station_name)
    except BusinessException as e:
        return await message.reply(content=e.message)
    media_info = await upload_media(media_type='image', media_url=img_url, **kwargs)
    return await message.reply(media=media_info)


async def handle_query_wiki_climate(message: GroupMessage | C2CMessage, city_name: str, **kwargs):
    try:
        city_name = city_name.strip('"“”')
        pattern = r'^(?=.*[A-Za-z])[A-Za-z0-9_ ]+$'
        if not kwargs.get('l') and re.match(pattern, city_name):
            kwargs['l'] = 'en'
        lang = kwargs.get('l', 'zh')
        wikipedia.set_lang(lang)
        group_id, user_id = get_group_and_user_id(message)

        try:
            page = wikipedia.page(city_name)
        except DisambiguationError as e:
            content = f'{city_name} 可以指以下内容:（回复序号即可）\n'
            option_str = await save_context_command(user_id=user_id, group_id=group_id, cache=kwargs.get('_bot').cache,
                                                    command_list=[f'气候 "{city}"' for city in
                                                                  e.options], )
            return await message.reply(content=content + option_str)
        except PageError as e:
            search_result_words = wikipedia.search(city_name)
            if search_result_words:
                page = wikipedia.page(search_result_words[0])
            else:
                return await message.reply(content=f'没有找到任何关于"{city_name}"的内容 使用语言:{lang}')
        tree = etree.HTML(page.html())
        table_elements = tree.xpath(
            "//table[contains(., '日均气温') or contains(., 'Climate data for') or contains(., '日均氣溫')]")
        if not table_elements:
            return await message.reply(content=f'未找到城市“{city_name}”的气候表格')
        save_path = os.path.join(os.getenv("WORK_DIR"), f'data/temp/climate_{city_name}_{uuid4()}.png')
        try:
            dom_to_image(table_elements[0], save_path=save_path, size=(1000, 680), )
        except Exception as e:
            logger.error(e)
            return await message.reply(content='生成气候图失败')
        return await reply_image_message(image_path=save_path, message=message, text=f'{city_name}气候')
    except Exception as e:
        logger.error(e)
        raise e
