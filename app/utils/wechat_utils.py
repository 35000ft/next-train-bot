import asyncio
import logging
import os
import time
from datetime import datetime

import httpx

from app.schemas.weixin import WechatMedia
from app.service.file_service import cache_uploaded_file
from app.utils.time_utils import end_of_date_timestamp

appid = os.getenv('WECHAT_ID')
app_secret = os.getenv('APPSECRET')
access_token = {
    'token': None,
    'expire_time': 0,
}

get_token_lock = asyncio.Lock()

logger = logging.getLogger(__name__)


async def get_access_token():
    # 校验过期时间
    current_time = time.time()
    if access_token['token'] and current_time < access_token['expire_time']:
        return access_token['token']
    url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={app_secret}'
    resp = httpx.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    async with get_token_lock:
        try:
            resp.raise_for_status()
            j_obj = resp.json()
            access_token['token'] = j_obj['access_token']
            access_token['expire_time'] = time.time() + j_obj['expires_in']
            return access_token['token']
        except Exception as e:
            logger.error(f'get access_token failed, err:{e}', )


async def upload_media(media_type: str = 'image', media_url: str = None, media_path: str = None,
                       cache_file=True, **kwargs) -> dict:
    """
    上传临时文件到公众号
    :param cache_file: 是否缓存文件
    :param media_type: image | voice | video
    :param media_url:
    :param media_path:
    :return: {
        "type": "image",
        "media_id": "MrFoQDpU3IncfOhIfJ8QNddYdo90uLQB7XGvcJS3mPBOMo0RD_4P9iUtr2hjIeJu",
        "created_at": 1749455627,
        "item": [ ]
        }
    """
    token = await get_access_token()
    filename = kwargs.get('filename')
    url = f'https://api.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type={media_type}'
    async with httpx.AsyncClient() as _client:
        if media_path:
            # 如果提供了media_path，则直接读取本地文件
            if not os.path.exists(media_path):
                raise FileNotFoundError(f"The file at {media_path} does not exist.")
            files = {'media': (filename or os.path.basename(media_path), open(media_path, 'rb'))}
        elif media_url:
            # 如果提供了media_url，则需要下载文件
            response = await _client.get(media_url)
            if response.status_code != 200:
                raise Exception(f"Failed to download file from {media_url}, status code: {response.status_code}")
            files = {'media': (filename or 'downloaded_file', response.content)}
        else:
            raise ValueError("Either media_path or media_url must be provided.")
        resp = await _client.post(url,
                                  headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'multipart/form-data;', },
                                  files=files)
        resp.raise_for_status()

    for file in files.values():
        file[1].close()

    media_info: WechatMedia = WechatMedia(**resp.json())
    if cache_file:
        cache_key = kwargs.get('cache_key', media_path or media_url)
        expire_at = kwargs.get('expire_at', end_of_date_timestamp(_date=datetime.now()))
        await cache_uploaded_file(key=cache_key, media=media_info, expire_at=expire_at)
