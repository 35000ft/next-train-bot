from botpy import logging
from botpy.message import C2CMessage, GroupMessage

logger = logging.get_logger()


class BusinessException(Exception):
    def __init__(self, message):
        self.message = message


class InputException(Exception):
    def __init__(self, message):
        self.message = message


class PermissionException(Exception):
    def __init__(self, message: str = None):
        self.message = message


async def exception_handler(message: GroupMessage | C2CMessage, exc: Exception):
    if isinstance(exc, InputException):
        return await message.reply(content=f'输入异常:{exc.message}')
    elif isinstance(exc, BusinessException):
        return await message.reply(content=exc.message)
    elif isinstance(exc, PermissionException):
        return await message.reply(content='无权限操作')
    else:
        logger.exception(exc)
        return await message.reply(content='指令无效哦', msg_seq=message.msg_seq)
