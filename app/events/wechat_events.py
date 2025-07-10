from typing import Optional

from botpy import logging
from botpy.message import GroupMessage

from app.config import get_db_session
from app.models.auth import BotUser
from app.schemas.auth import UserCreate
from app.service.user_service import create_user
from app.utils.common import command_wrapper, generate_username
from app.utils.exceptions import BusinessException
from app.utils.security_utils import generate_invite_code

logger = logging.get_logger()


async def handle_register(message: GroupMessage, invite_code: str, username: str, **kwargs):
    now_invite_code = generate_invite_code('NKG-TRANS')
    if invite_code != now_invite_code:
        return await message.reply(content='邀请码无效')
    form = UserCreate(username=username or generate_username(), openid=message.author.member_openid)
    try:
        async with get_db_session() as session:
            bot_user: BotUser = await create_user(session, form)
    except BusinessException as e:
        return await message.reply(content=f'注册失败: {e.message}')
    return await message.reply(content=f'注册成功，你的用户名为:{bot_user.username}')


# @command_wrapper(help='推文 客流月报(按关键词搜索推文) | 推文 list(查询近期推文)')
async def handle_query_wechat_article(message: GroupMessage, **kwargs):
    pass


# @command_wrapper(help='添加推文 <推文URL> [关键词](仅限有权限的用户)')
async def handle_add_auto_reply_wechat_article(message: GroupMessage, **kwargs):
    pass
