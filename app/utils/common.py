import functools
import time

from botpy import logging
from botpy.message import GroupMessage

from app.schemas.weixin import ResponseMsgBody, WechatMedia
from app.utils.exceptions import InputException

logger = logging.get_logger()


def command_wrapper(**kwargs):
    def decorator(func):
        func.__help = kwargs.get('help')

        @functools.wraps(func)
        async def wrapper(*args, **_kwargs):
            message: GroupMessage = args[0]
            try:
                return await func(*args, **_kwargs)
            except TypeError as e:
                error_msg = str(e)
                if "missing" in error_msg and "required positional argument" in error_msg:
                    logger.exception(f'type error:{e}', exc_info=e)
                    _help = kwargs.get('help')
                    return await message.reply(content=f'指令格式有误，样例:{_help}')
                else:
                    raise e
            except InputException as e:
                _help = kwargs.get('help')
                return await message.reply(content=f'{e.message}，样例:{_help}')

        return wrapper

    return decorator


class WechatMessage(GroupMessage):
    def __init__(self, user_id: str, data: dict, ):
        super().__init__(None, int(time.time()), data)
        user_dict = {
            'member_openid': user_id,
        }
        self.author = self._User(user_dict)
        self.group_openid = data.get("group_openid", None)
        self.to_username = data.get("to_username", None)
        self.content = data.get("content", None)

    async def reply(self, **kwargs) -> ResponseMsgBody:
        resp = ResponseMsgBody(
            ToUserName=self.author.member_openid,
            FromUserName=self.to_username,
            CreateTime=int(time.time()),
            MsgType="text",
            Content=kwargs.get("content", None))
        if media_info := kwargs.get("media"):
            if isinstance(media_info, WechatMedia):
                resp.set_media(media_info)
        return resp
