import re

from botpy.message import GroupMessage, C2CMessage


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


# def parse_command(message_text: str):
#     if not message_text:
#         return None, None
#     _split = message_text.strip().strip('/').split(' ')
#     _split = [x.strip() for x in _split]
#
#     if len(_split) == 0:
#         return None, None
#
#     command = _split[0]
#     argv = [x.strip('-') for x in _split[1:] if x.startswith('-')]
#     params = [x for x in _split[1:] if not x.startswith('-')]
#     return command, params, argv
#

def get_group_and_user_id(message: GroupMessage | C2CMessage, ):
    group_id = message.group_openid if isinstance(message, GroupMessage) else None
    user_id = message.author.member_openid
    return group_id, user_id


def is_http_url(url):
    if not url:
        return False
    regex = r"^(http|https)://((([A-Z0-9][A-Z0-9-]{0,61}[A-Z0-9])\.)+[A-Z]{2,6}\.?|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?(/?|[/?]\S+)$"
    return re.match(regex, url, re.IGNORECASE) is not None
