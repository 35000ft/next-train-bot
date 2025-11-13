import json
from typing import List, Optional

from async_lru import alru_cache
from botpy import logging
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import select, or_

from app.config import get_db_session
from app.models.Railsystem import PersonalConfig
from app.schemas import railsystem

logger = logging.get_logger()


@alru_cache(maxsize=64, ttl=600)
async def get_default_railsystem_code(group_id: str, user_id: str) -> str | None:
    if not group_id and not user_id:
        return None
    result: List[PersonalConfig] = await query_personal_config(category_key='GROUP_DEFAULT_RAILSYSTEM_CODE',
                                                               user_id=user_id, group_id=group_id, is_list=True)
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
        pc_instance = await query_personal_config(category_key=category_key, user_id=user_id,
                                                  is_list=False)
        async with get_db_session() as session:
            if pc_instance is None:
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
                pc_instance.params = railsystem_code
            await session.commit()


@alru_cache(maxsize=64, ttl=60)
async def get_station_by_user_station_alias(alias_name: str, user_id: str) -> railsystem.Station | bool:
    station_j_obj: dict = await query_personal_config(category_key='STATION_ALIAS', user_id=user_id, name=alias_name,
                                                      is_list=False, decode_params_type='json')
    if station_j_obj:
        return railsystem.Station(**station_j_obj)


async def add_station_name_alias(alias_name: str, user_id: str, station: railsystem.Station):
    async with get_db_session() as session:
        p = PersonalConfig(user_id=user_id, name=alias_name, category_key='STATION_ALIAS', status=1,
                           params=station.model_dump_json())
        session.add(p)
        await session.commit()


async def query_personal_config(category_key: str, user_id: str = None, group_id: str = None,
                                name: str = None, is_list=True, decode_params_type: str | PydanticBaseModel = None) -> (
        Optional[PersonalConfig] | List[PersonalConfig] | str | dict | list | PydanticBaseModel):
    if not user_id and not group_id:
        raise Exception('user_id or group_id is required')
    async with get_db_session() as session:
        stmt = select(PersonalConfig).where(PersonalConfig.status == 1, PersonalConfig.category_key == category_key)
        if user_id:
            stmt = stmt.where(or_(PersonalConfig.user_id == user_id, PersonalConfig.group_id == group_id))
        elif group_id:
            stmt = stmt.where(PersonalConfig.group_id == group_id)
        if name:
            stmt = stmt.where(PersonalConfig.name == name)
        result = await session.execute(stmt)
        if is_list:
            return list(result.scalars().all())
        else:
            p: PersonalConfig = result.scalar_one_or_none()
            if not p:
                return None
            if decode_params_type == 'text':
                return p.params
            elif decode_params_type == 'json':
                if p.params:
                    return json.loads(p.params)
                else:
                    return None
            elif isinstance(decode_params_type, PydanticBaseModel):
                return decode_params_type.model_validate_json(p.params)
            return p


@alru_cache(maxsize=64, ttl=3600)
async def get_command_dict_by_group_id(group_id: str) -> dict:
    try:
        p: dict = await query_personal_config(category_key='GROUP_COMMAND_DICT', group_id=group_id, is_list=False,
                                              decode_params_type='json')
        return p
    except Exception as e:
        logger.warning('decode as dict error', exc_info=e)
        return {}
