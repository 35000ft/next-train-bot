from datetime import datetime
from zoneinfo import ZoneInfo

from async_lru import alru_cache
from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.service.file_service import cache_uploaded_file, get_cached_uploaded_file
from app.utils.time_utils import end_of_date_timestamp


async def get_star_party(message: GroupMessage | C2CMessage, **kwargs):
    now_gmt8: datetime = datetime.now(tz=ZoneInfo("Asia/Shanghai"))
    cache_key = f'starparty:{now_gmt8.strftime("%Y-%m-%d")}'

    upload_media = None
    cache_upload_media = await get_cached_uploaded_file(cache_key)
    if not cache_upload_media:
        star_party_latest_url = 'http://aunu.steveling.cn/latest.jpg'
        upload_media = await message._api.post_group_file(group_openid=message.group_openid, file_type=1,
                                                          url=star_party_latest_url)

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
