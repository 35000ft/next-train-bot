import os

from botpy.message import GroupMessage, C2CMessage


def get_group_and_user_id(message: GroupMessage | C2CMessage, ):
    group_id = message.group_openid if isinstance(message, GroupMessage) else None
    user_id = message.author.member_openid if isinstance(message, GroupMessage) else message.author.user_openid
    return group_id, user_id
