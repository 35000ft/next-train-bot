import re
from typing import List

import jieba
from botpy import logging

from app.utils.exceptions import BusinessException

logger = logging.get_logger()
has_inited_jieba = False


def try_cut_command(input_string: str, accepted_commands: List[str]) -> List[str]:
    global has_inited_jieba
    if not has_inited_jieba:
        for x in accepted_commands:
            jieba.add_word(x)
        has_inited_jieba = True
    return jieba.lcut(input_string)


def parse_command(input_string: str, **kwargs):
    accepted_commands = kwargs.get('accepted_commands', [])
    if not input_string:
        return None, None
    _split = input_string.strip().strip('/').split(' ')
    parts = [x.strip() for x in _split]

    if len(parts) == 0:
        return None, None, None
    if len(parts) == 1:
        if accepted_commands:
            if parts[0] in accepted_commands:
                return parts[0], [], {}
            else:
                parts = try_cut_command(parts[0], accepted_commands)
        else:
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


def is_http_url(url):
    if not url:
        return False
    regex = r"^(http|https)://((([A-Z0-9][A-Z0-9-]{0,61}[A-Z0-9])\.)+[A-Z]{2,6}\.?|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?(/?|[/?]\S+)$"
    return re.match(regex, url, re.IGNORECASE) is not None


async def save_context_command(user_id: str, group_id: str, command_list: List[str], **kwargs):
    def build_option_dict():
        _option_dict = {}
        _reply_content = ""
        for index, _command in enumerate(command_list):
            _index = str(index + 1)
            _option_dict[_index] = _command
            _reply_content += f"{_index}. {_command}\n"
        return _option_dict, _reply_content

    cache = kwargs.get('cache')
    if not command_list:
        logger.warning("Can not set empty option_dict")
        return
    key = user_id
    if isinstance(group_id, str):
        key = key + "-" + group_id
    option_dict, options_str = build_option_dict()
    await cache.set(key, option_dict)
    return options_str


async def find_context_command(user_id: str, group_id: str, option_str: str, **kwargs):
    cache = kwargs.get('cache')
    if not cache:
        raise BusinessException('指令有误')
    key = user_id
    if isinstance(group_id, str):
        key = key + "-" + group_id
    options: dict = await cache.get(key)
    if options:
        command = options.get(option_str.strip())
        if command:
            return command
        else:
            raise BusinessException('指令有误')
    else:
        raise BusinessException("没有可用的context指令选项")
