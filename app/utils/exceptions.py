from botpy import logging
from botpy.message import C2CMessage, GroupMessage

logger = logging.get_logger()


class BusinessException(Exception):
    def __init__(self, message):
        self.message = message


class InputException(Exception):
    def __init__(self, message):
        self.message = message


async def exception_handler(message: GroupMessage | C2CMessage, exc: Exception):
    if isinstance(exc, InputException):
        await message.reply(content=f'输入异常:{exc.message}')
    if isinstance(exc, TypeError):
        logger.exception(exc)
        await message.reply(content='指令有误')
    elif isinstance(exc, BusinessException):
        await message.reply(content=exc.message, msg_seq=10)
    else:
        logger.exception(exc)
        await message.reply(content='指令无效哦', msg_seq=message.msg_seq)
