import datetime as dt
import mimetypes
import os
import time
from datetime import datetime

import aiofiles
import httpx
from botpy import logging
from botpy.types import message

from app.utils.img_utils import image_to_base64

uploaded_file_cache = {}
max_cache_files = 128
ttl = 3600

logger = logging.get_logger()


async def cache_uploaded_file(key: str, media: message.Media, expire_at: float | int = None):
    now = time.time()
    logger.info(f'cache file key:{key}')

    media['expires_at'] = expire_at or now + ttl

    # If key already exists, update its media information
    if key in uploaded_file_cache:
        uploaded_file_cache[key] = media
        return

    # If cache is not full, add the new media directly.
    if len(uploaded_file_cache) < max_cache_files:
        uploaded_file_cache[key] = media
        return

    # Remove expired entries first.
    expired_keys = [k for k, m in uploaded_file_cache.items() if m['expires_at'] <= now]
    for k in expired_keys:
        del uploaded_file_cache[k]

    # If after cleaning expired entries the cache has room, add the media.
    if len(uploaded_file_cache) < max_cache_files:
        uploaded_file_cache[key] = media
        return

    # Cache is still full: find and evict the entry that will expire the soonest.
    evict_key = min(uploaded_file_cache, key=lambda k: uploaded_file_cache[k]['expires_at'])
    del uploaded_file_cache[evict_key]

    # Finally, add the new media.
    uploaded_file_cache[key] = media


async def get_cached_uploaded_file(key: str) -> message.Media | None:
    if not key:
        return None
    now = time.time()
    _cached = uploaded_file_cache.get(key, None)
    if not _cached:
        return None
    if not _cached['expires_at']:
        clean_expired()
        return None
    expires_at_ = _cached["expires_at"]
    if _cached['expires_at'] < now:
        logger.info(f'Cache key {key} expired, at {expires_at_}')
        return None
    logger.info(
        f'Cache hit:{key} expire in {expires_at_ - now}, utc time:{datetime.fromtimestamp(expires_at_, dt.UTC)}')
    return _cached


def clean_expired():
    now = time.time()
    for k in uploaded_file_cache.keys():
        expires_at = uploaded_file_cache[k]['expires_at']
        if not expires_at:
            del uploaded_file_cache[k]
        if expires_at < now:
            del uploaded_file_cache[k]


async def download_and_save_image(img_url: str, file_name: str, sub_folder: str) -> str:
    work_dir = os.getenv("WORK_DIR")
    if not work_dir:
        raise Exception("WORK_DIR 环境变量未设置")

    posts_dir = os.path.join(work_dir, "data", sub_folder)
    os.makedirs(posts_dir, exist_ok=True)
    local_file_path = os.path.join(posts_dir, file_name)
    _headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    }

    # 狗腾讯只支持tls1.2
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(img_url.replace('https:', 'http:'), headers=_headers)
        if response.status_code == 200:
            content = response.content
            # 假设 response 是请求返回的对象
            content_type = response.headers.get("Content-Type", "")
            extension = mimetypes.guess_extension(content_type)

            # 如果能够根据 MIME 类型猜出扩展名，则更新文件保存路径
            if extension:
                # 可以选择判断 local_file_path 是否已经有扩展名，或者直接追加
                local_file_path = local_file_path + extension
            async with aiofiles.open(local_file_path, "wb") as f:
                await f.write(content)
                relative_file_path = os.path.join('data', sub_folder, file_name).replace('\\', '/') + (extension or '')
                logger.info(f'save image:{relative_file_path}')
                return relative_file_path
        else:
            logger.error(f'failed to download {img_url}')
            raise Exception(f"下载图片失败, 状态码: {response.status_code} url:{img_url}")


async def get_local_image(file_path: str, base_path: str = os.getenv('WORK_DIR')):
    _file_path = os.path.join(base_path, file_path)
    logger.info(f'get local image:{_file_path}')
    if os.path.exists(_file_path):
        return image_to_base64(_file_path)
