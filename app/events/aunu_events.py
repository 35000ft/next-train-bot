from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from async_lru import alru_cache
from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.schemas.APOD import APOD, BjpApodFetcher, NasaApodFetcher
from app.service.file_service import cache_uploaded_file, get_cached_uploaded_file
from app.utils.time_utils import end_of_date_timestamp, parse_date

logger = logging.get_logger()


async def get_star_party(message: GroupMessage | C2CMessage, target_date_str: str = None, **kwargs):
    async def fetch_latest():
        _url = 'http://aunu.steveling.cn/latest.jpg'
        _upload_media = await message._api.post_group_file(group_openid=message.group_openid, file_type=1,
                                                           url=_url)
        return _upload_media

    async def fetch_date(__date: datetime):
        _url = f'http://aunu.steveling.cn/{__date.strftime("%Y%m")}/{__date.day}.jpg'
        _upload_media = await message._api.post_group_file(group_openid=message.group_openid, file_type=1,
                                                           url=_url)
        return _upload_media

    now_gmt8 = datetime.now(tz=ZoneInfo("Asia/Shanghai"))
    if not target_date_str:
        _date: datetime = now_gmt8
        _date_str: str = _date.strftime("%Y-%m-%d")
    else:
        _date: datetime = parse_date(target_date_str)
        _date_str: str = _date.strftime("%Y-%m-%d")
    cache_key = f'starparty:{_date_str}'

    upload_media = None
    cache_upload_media = await get_cached_uploaded_file(cache_key) if not kwargs.get('update') else None
    if not cache_upload_media:
        try:
            if not target_date_str:
                upload_media = await fetch_latest()
            else:
                upload_media = await fetch_date(_date)
        except Exception as e:
            logger.error(f"获取starparty失败,err:{e}")
            await message.reply(content='获取starparty失败')
            return

    _temp = cache_upload_media or upload_media
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=7,
        msg_id=message.id,
        media=_temp,
        msg_seq=2,
    )
    if upload_media:
        await cache_uploaded_file(cache_key, upload_media, expire_at=end_of_date_timestamp(now_gmt8))


@alru_cache(maxsize=6, ttl=300)
async def get_apod(target_date: datetime = None, **kwargs) -> Optional[APOD]:
    fetcher = NasaApodFetcher() if kwargs.get('en') else BjpApodFetcher()
    if target_date:
        return await fetcher.fetch_date(target_date)
    return await fetcher.fetch_latest()


async def handle_get_apod(message: GroupMessage | C2CMessage, target_date_str: str = None, **kwargs):
    if target_date_str:
        try:
            target_date = parse_date(target_date_str)
        except Exception as e:
            await message.reply(content='不支持的日期格式')
            return
        apod = await get_apod(target_date=target_date, **kwargs)
    else:
        apod = await get_apod(**kwargs)
    if apod:
        _upload_media = await message._api.post_group_file(group_openid=message.group_openid, file_type=1,
                                                           url=apod.img_url)
        await message._api.post_group_message(
            content=apod.to_bot_reply(),
            group_openid=message.group_openid,
            msg_type=7,
            msg_id=message.id,
            media=_upload_media,
            msg_seq=2,
        )
    else:
        await message.reply(content='找不到这个apod')
