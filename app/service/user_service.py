from typing import Optional, List

from passlib.context import CryptContext
from sqlalchemy import or_, join, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.config import get_db_session
from app.models.auth import *
from app.schemas.auth import UserCreate
from app.utils.AsyncLRUCache import AsyncLRUCache
from app.utils.common import WechatMessage
from app.utils.exceptions import BusinessException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
login_users = AsyncLRUCache(maxsize=2048)


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
        is_active=True
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
            BotUser.is_active == True,
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


async def authorize(message: WechatMessage, permission_key: str, param: str = None) -> bool:
    if not permission_key:
        return True
    bot_user: BotUser = message.bot_user
    if not bot_user:
        return False
    async with get_db_session() as session:
        permissions = await get_user_permission(session, user_id=bot_user.id)
