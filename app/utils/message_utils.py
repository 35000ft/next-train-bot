from botpy.http import Route
from botpy.message import GroupMessage, C2CMessage

from app.service.file_service import get_local_image


async def send_image_message(_message):
    pass


async def post_group_base64_file(
        _message: GroupMessage,
        group_openid: str,
        file_type: int,
        file_data: str,
        srv_send_msg: bool = False,
):
    """
    上传/发送群聊图片

    Args:
      group_openid (str): 您要将消息发送到的群的 ID
      file_type (int): 媒体类型：1 图片png/jpg，2 视频mp4，3 语音silk，4 文件（暂不开放）
      url (str): 需要发送媒体资源的url
      srv_send_msg (bool): 设置 true 会直接发送消息到目标端，且会占用主动消息频次
    """
    payload = locals()
    payload.pop("_message", None)
    route = Route("POST", "/v2/groups/{group_openid}/files", group_openid=group_openid)
    return await _message._api._http.request(route, json=payload)


async def reply_image_message(image_path: str, message: GroupMessage | C2CMessage, text: str = None, **kwargs):
    base64_data = await get_local_image(image_path)
    if not base64_data:
        await message.reply(content=kwargs.get('on_not_found', '无效的文件'))
        return

    upload_media = await post_group_base64_file(
        _message=message,
        file_data=base64_data,
        group_openid=message.group_openid,
        file_type=1,
    )
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=7,
        msg_id=message.id,
        content=text,
        media=upload_media,
        msg_seq=2,
    )
