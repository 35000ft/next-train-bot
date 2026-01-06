import base64
import os

import requests
from botpy import logging
from botpy.message import GroupMessage, C2CMessage
import urllib.parse

from app.utils.message_utils import post_group_base64_file

logger = logging.get_logger()


async def handle_query_map_tile(message: GroupMessage | C2CMessage, address: str, **kwargs):
    url = urllib.parse.urljoin(os.getenv('METROTRACE_API_BASEURL'), 'common/osm/address2tile')
    resp = requests.get(url, params={
        'q': address,
        'z': kwargs.get('z', 14),
    })
    logger.info(f'GET {resp.url} {resp.status_code}')
    if resp.status_code == 200:
        content_bytes = resp.content  # bytes
        b64_str = base64.b64encode(content_bytes).decode('utf-8')
        upload_media = await post_group_base64_file(
            _message=message,
            file_data=b64_str,
            group_openid=message.group_openid,
            file_type=1,  # 文件类型要对应上，具体支持的类型见方法说明
        )
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=7,
            msg_id=message.id,
            media=upload_media,
            content=f'{address} 在OpenStreetMap中的结果'
        )
    else:
        await message.reply(content='请求地址转地图瓦片失败')
