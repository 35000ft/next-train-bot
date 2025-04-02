from app.config import get_db_session
from sqlalchemy import select, or_, exists

from app.models.Railsystem import PersonalConfig


async def get_default_railsystem_code(group_id: str, user_id: str) -> str | None:
    if not group_id and not user_id:
        return None
    async with get_db_session() as session:
        stmt = select(PersonalConfig).where(PersonalConfig.status == 1)
        if user_id:
            stmt = stmt.where(or_(PersonalConfig.user_id == user_id, PersonalConfig.group_id == group_id))
        elif group_id:
            stmt = stmt.where(PersonalConfig.group_id == group_id)

        result = await session.execute(stmt)
        result = result.scalars().all()
        if len(result) == 0:
            return None
        elif len(result) == 1:
            return result[0].params or None
        elif user_id and len(result) > 0:
            user_default_group = list(filter(lambda r: r.user_id == user_id, result))
            if len(user_default_group) == 1:
                return user_default_group[0].params
            else:
                user_group_default_group = list(
                    filter(lambda r: r.user_id == user_id and r.group_id == group_id, result))
                if not user_group_default_group:
                    return result[0].params
                else:
                    return user_group_default_group[0].params


async def set_default_railsystem_code(group_id: str | None, user_id: str, railsystem_code: str, **kwargs) -> None:
    if railsystem_code:
        category_key = 'GROUP_DEFAULT_RAILSYSTEM_CODE'
        async with get_db_session() as session:
            # 直接查询记录是否存在
            stmt = select(PersonalConfig).where(
                PersonalConfig.group_id == group_id,
                PersonalConfig.user_id == user_id,
                PersonalConfig.category_key == category_key
            )
            result = await session.execute(stmt)
            pc_instance = result.scalar_one_or_none()  # 如果不存在则返回 None

            if pc_instance is None:
                # 记录不存在则创建新记录
                new_pc = PersonalConfig(
                    name=f'{kwargs.get("name", user_id)}的默认线网',
                    category_key=category_key,
                    status=1,
                    user_id=user_id,
                    group_id=group_id,
                    params=railsystem_code
                )
                session.add(new_pc)
            else:
                # 记录已存在则更新 params 字段
                pc_instance.params = railsystem_code

            await session.commit()
