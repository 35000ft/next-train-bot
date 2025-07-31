import functools
import importlib
import time

from botpy import logging
from botpy.message import GroupMessage

from app.models.auth import BotUser
from app.schemas.wechat import ResponseMsgBody, WechatMedia
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


def dynamic_import(full_path: str):
    """
        动态导入模块或模块中的对象。
        full_path 可以是:
            - 'package.module' （返回模块）
            - 'package.module:object' 或 'package.module.object'（返回模块中的对象）
        """
    if ':' in full_path:
        module_path, attr = full_path.split(':', 1)
    elif '.' in full_path:
        parts = full_path.split('.')
        for i in range(len(parts), 0, -1):
            try:
                module_path = '.'.join(parts[:i])
                attr_path = parts[i:]
                module = importlib.import_module(module_path)
                obj = module
                for a in attr_path:
                    obj = getattr(obj, a)
                return obj
            except (ModuleNotFoundError, AttributeError):
                continue
        raise ImportError(f"Could not import from path: {full_path}")
    else:
        # fallback - just import whole module
        module_path = full_path
        attr = None

    module = importlib.import_module(module_path)
    return getattr(module, attr) if 'attr' in locals() else module


class WechatMessage(GroupMessage):
    def __init__(self, user_id: str, data: dict, bot_user: BotUser = None):
        super().__init__(None, int(time.time()), data)
        user_dict = {
            'member_openid': user_id,
        }
        self.author = self._User(user_dict)
        self.group_openid = data.get("group_openid", None)
        self.to_username = data.get("to_username", None)
        self.content = data.get("content", None)
        self.bot_user = bot_user

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
