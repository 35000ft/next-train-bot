import functools
from botpy import logging
from typing import Optional, List

from passlib.context import CryptContext
from sqlalchemy import or_, join, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.auth import *
from app.schemas.auth import UserCreate
from app.utils.AsyncLRUCache import AsyncLRUCache
from app.utils.common import WechatMessage
from app.utils.exceptions import BusinessException, PermissionException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
login_users = AsyncLRUCache(maxsize=2048)

logger = logging.get_logger()


async def create_user(db: AsyncSession, user: UserCreate) -> BotUser:
    filters = [BotUser.username == user.username]
    if user.email:
        filters.append(BotUser.email == user.email)

    stmt = select(BotUser).where(or_(*filters))
    result = await db.execute(stmt)
    existing_user: Optional[BotUser] = result.scalar_one_or_none()

    if existing_user:
        if user.email and existing_user.email == user.email:
            raise BusinessException(f'邮箱已存在: {user.email}')
        if existing_user.username == user.username:
            raise BusinessException(f'用户名已存在: {user.username}')

    hashed_password = pwd_context.hash(user.password)
    db_user = BotUser(
        username=user.username,
        email=user.email,
        password=hashed_password,
        openid=user.openid,
        is_active=1
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def get_user_permission(db: AsyncSession, user_id: str | int) -> List[Permission]:
    stmt = (
        select(Permission)
        .select_from(
            join(UserRole, RolePermission, UserRole.role_id == RolePermission.role_id)
            .join(Permission, RolePermission.permission_id == Permission.id)
        )
        .where(UserRole.user_id == user_id)
        .where(UserRole.is_active == 1)
        .where(RolePermission.is_active == 1)
        .where(Permission.is_active == 1)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def query_user(db: AsyncSession, account: str) -> BotUser:
    bot_user = await login_users.get(account)
    if bot_user:
        return bot_user
    stmt = (
        select(BotUser)
        .where(and_(
            BotUser.is_active == 1,
            or_(
                BotUser.openid == account,
                BotUser.email == account
            )
        )))
    result = await db.execute(stmt)
    bot_user = result.scalars().one_or_none()
    if bot_user:
        permissions = await get_user_permission(db, bot_user.id)
        setattr(bot_user, 'permissions', permissions)
        await login_users.set(account, bot_user)
    return bot_user


def authorize(permission_key: str, param_getter=None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(message: WechatMessage, *args, **_kwargs):
            if not permission_key:
                return await func(message, *args, **_kwargs)
            bot_user: BotUser = message.bot_user
            if not bot_user:
                raise PermissionException()
            permissions: List[Permission] = bot_user.permissions
            if not permissions:
                raise PermissionException()
            param = None
            if param_getter:
                param = param_getter(message)
            has_permission = list(
                filter(lambda permission: permission.code == permission_key and permission.params == param,
                       permissions))
            logger.info(f'user:{bot_user.openid} permission key:{permission_key} param:{param}')
            if has_permission:
                return await func(message, *args, **_kwargs)
            else:
                raise PermissionException()

        return wrapper

    return decorator
