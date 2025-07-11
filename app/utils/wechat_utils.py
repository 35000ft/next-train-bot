import asyncio
import logging
import mimetypes
import os
import time
from datetime import datetime
from bs4 import BeautifulSoup

import httpx

from app.schemas.wechat import WechatMedia, Article
from app.service.file_service import cache_uploaded_file
from app.utils.time_utils import end_of_date_timestamp

token_store = {}
get_token_lock = asyncio.Lock()

logger = logging.getLogger(__name__)


def load_account_info(account: str) -> dict:
    token = os.getenv(f'{account}_WECHAT_TOKEN')
    wechat_id = os.getenv(f'{account}_WECHAT_ID')
    appsecret = os.getenv(f'{account}_APPSECRET')
    if not token or not wechat_id:
        raise Exception('account is not valid, cause no wechat token or wechat id provided')
    return {
        'wechat_token': token,
        'wechat_id': wechat_id,
        'appsecret': appsecret,
    }


async def get_access_token(account_info: dict):
    # 校验过期时间
    current_time = time.time()
    access_token = token_store.get(account_info['wechat_id'], {
        'token': None,
        'expire_time': 0,
    })

    if access_token['token'] and current_time < access_token['expire_time']:
        return access_token['token']
    url = f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={account_info['wechat_id']}&secret={account_info['appsecret']}'
    resp = httpx.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    async with get_token_lock:
        try:
            resp.raise_for_status()
            j_obj = resp.json()
            access_token['token'] = j_obj['access_token']
            access_token['expire_time'] = time.time() + j_obj['expires_in']
            token_store[account_info['wechat_id']] = access_token
            return access_token['token']
        except Exception as e:
            logger.error(f'get access_token failed, err:{e}', )


async def upload_media(media_type: str = 'image', media_url: str = None, media_path: str = None,
                       cache_file=True, **kwargs) -> WechatMedia:
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
    token = await get_access_token(kwargs.get('account'))
    filename = kwargs.get('filename')
    url = f'https://api.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type={media_type}'
    async with httpx.AsyncClient() as _client:
        if media_path:
            # 如果提供了media_path，则直接读取本地文件
            if not os.path.exists(media_path):
                raise FileNotFoundError(f"The file at {media_path} does not exist.")
            filename = filename or os.path.basename(media_path)
            name, extension = os.path.splitext(media_path)
            if not extension:
                extension = mimetypes.guess_extension(media_path)
                filename += extension
            files = {'media': (filename, open(media_path, 'rb'))}
        elif media_url:
            # 如果提供了media_url，则需要下载文件
            response = await _client.get(media_url)
            if response.status_code != 200:
                raise Exception(f"Failed to download file from {media_url}, status code: {response.status_code}")
            content_type = response.headers.get('Content-Type')
            if content_type:
                mime_type = content_type.split(';')[0]
                extension = mimetypes.guess_extension(mime_type)
            files = {'media': (filename or f'downloaded_file.{extension}', response.content)}
        else:
            raise ValueError("Either media_path or media_url must be provided.")
        resp = await _client.post(url,
                                  headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'multipart/form-data;', },
                                  files=files)
        resp.raise_for_status()
        j_obj = resp.json()
        if 'errcode' in j_obj:
            logger.error(f'upload media failed, err:{j_obj}')
            raise Exception(f'Failed to upload media,{j_obj}')
    media_info: WechatMedia = WechatMedia(**j_obj)
    if cache_file:
        cache_key = kwargs.get('cache_key', media_path or media_url)
        expire_at = kwargs.get('expire_at', end_of_date_timestamp(_date=datetime.now()))
        await cache_uploaded_file(key=cache_key, media=media_info, expire_at=expire_at)
    return media_info


async def get_article(url: str) -> Article:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        })
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    meta_tag = soup.find('meta', attrs={'property': 'og:title'})
    title = meta_tag.get('content') if meta_tag else None
    meta_tag = soup.find('meta', attrs={'name': 'author'})
    author = meta_tag.get('content') if meta_tag else None
    meta_tag = soup.find('meta', attrs={'name': 'description'})
    description = meta_tag.get('content') if meta_tag else ''
    img_tag = soup.find('img', attrs={'class': 'wx_follow_avatar_pic', 'alt': 'cover_image'})
    head_img = None
    if img_tag:
        head_img = img_tag.get('src')
    return Article(Description=description, Title=title, PicUrl=head_img, Author=author)
