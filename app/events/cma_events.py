from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.events.cma_weather.radar import get_radar_image

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
