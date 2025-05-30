from botpy import logging
from botpy.message import C2CMessage, GroupMessage
from sqlalchemy import select

from app.config import get_db_session
from app.models.auth import UserGroupRel, BotUser
from app.schemas.auth import UserCreate
from app.service.user_service import create_user
from app.utils.exceptions import SomethingExistException
from app.utils.qqbot_utils import get_group_and_user_id
from app.utils.security_utils import CodeManager

logger = logging.get_logger()


async def handle_signup(message: C2CMessage, username: str, **kwargs):
    email = kwargs.get('e')
    openid = message.author.user_openid
    form = UserCreate(username=username, email=email, openid=openid)
    async with get_db_session() as session:
        try:
            user = await create_user(session, form)
            await message.reply(content=f'注册成功, 用户名为:{user.username}')
        except SomethingExistException as e:
            await message.reply(content=e.message)
            return
        except Exception as e:
            logger.exception(e)
            await message.reply(content='注册失败')
            return


async def handle_connect_group(message: C2CMessage, **kwargs):
    # 关联群组
    bot = kwargs.get('_bot')
    code_manager: CodeManager = bot.code_manager
    user_open_id = message.author.user_openid
    code = code_manager.generate_code(user_open_id)
    await message.reply(content=f'请在需要关联的群组输入以下指令: 关联 {code}')


async def handle_validate_connect_group(message: GroupMessage, code: str, **kwargs):
    bot = kwargs.get('_bot')
    code_manager: CodeManager = bot.code_manager
    user_open_id = code_manager.validate_code(code)
    if not user_open_id:
        await message.reply(content='验证码已过期, 请重新私聊bot获取, 指令为: 关联')
        return
    group_openid, group_user_openid = get_group_and_user_id(message)
    async with get_db_session() as session:
        stmt = select(BotUser).where(BotUser.openid == user_open_id)
        result = await session.execute(stmt)
        user: BotUser = result.scalar_one_or_none()
        if not user:
            await message.reply(content='该用户未注册, 请先私聊bot注册, 指令为：注册 <用户名>')
            return
        rel = UserGroupRel(user_id=user.id, user_openid=user.openid, group_openid=group_openid,
                           group_user_openid=group_user_openid)
        session.add(rel)
        await session.commit()
    await message.reply(content='关联群组成功')
