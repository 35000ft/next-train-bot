import re

from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.utils.exceptions import BusinessException

logger = logging.get_logger()


def parse_command(input_string):
    if not input_string:
        return None, None
    _split = input_string.strip().strip('/').split(' ')
    parts = [x.strip() for x in _split]

    if len(parts) == 0:
        return None, None, None
    if len(parts) == 1:
        return parts[0], [], {}
    _command = parts[0]
    seq_params = []
    named_params = {}
    i = 1
    while i < len(parts):
        part = parts[i]
        # 处理没有命令名的参数
        if not part.startswith('-'):
            seq_params.append(part)
        elif part.startswith('-'):
            command = part.strip('-')
            if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                named_params[command] = parts[i + 1]
                i += 1  # 跳过参数
            else:
                named_params[command] = True
        i += 1
    return _command, seq_params, named_params


def get_group_and_user_id(message: GroupMessage | C2CMessage, ):
    group_id = message.group_openid if isinstance(message, GroupMessage) else None
    user_id = message.author.member_openid
    return group_id, user_id


def is_http_url(url):
    if not url:
        return False
    regex = r"^(http|https)://((([A-Z0-9][A-Z0-9-]{0,61}[A-Z0-9])\.)+[A-Z]{2,6}\.?|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?(/?|[/?]\S+)$"
    return re.match(regex, url, re.IGNORECASE) is not None


async def save_context_command(user_id: str, group_id: str, option_dict: dict, **kwargs):
    cache = kwargs.get('cache')
    if not option_dict:
        logger.warning("Can not set empty option_dict")
        return
    key = user_id
    if isinstance(group_id, str):
        key = key + "-" + group_id
    await cache.set(key, option_dict)


async def find_context_command(user_id: str, group_id: str, option_str: str, **kwargs):
    cache = kwargs.get('cache')
    key = user_id
    if isinstance(group_id, str):
        key = key + "-" + group_id
    options: dict = await cache.get(key)
    command = options.get(option_str.strip())
    if command:
        return command
    else:
        raise BusinessException('指令有误')
