from typing import Optional

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.auth import BotUser
from app.schemas.auth import UserCreate
from passlib.context import CryptContext

from app.utils.exceptions import SomethingExistException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_user(db: AsyncSession, user: UserCreate) -> BotUser:
    filters = [BotUser.username == user.username]
    if user.email:
        filters.append(BotUser.email == user.email)

    stmt = select(BotUser).where(or_(*filters))
    result = await db.execute(stmt)
    existing_user: Optional[BotUser] = result.scalar_one_or_none()

    if existing_user:
        if user.email and existing_user.email == user.email:
            raise SomethingExistException(f'邮箱已存在: {user.email}')
        if existing_user.username == user.username:
            raise SomethingExistException(f'用户名已存在: {user.username}')

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
