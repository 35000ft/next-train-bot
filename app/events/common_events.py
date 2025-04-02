from typing import List, Dict, Tuple

from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.models.Railsystem import Station
from app.schemas import RailsystemSchemas
from app.service.personaliz_service import get_default_railsystem_code
from app.service.railsystem_service import get_station_detail_byid, get_station_by_keyword
from app.utils.command_utils import get_group_and_user_id

logger = logging.get_logger()


async def handle_get_station_by_name(message: GroupMessage | C2CMessage, station_name: str, **kwargs) -> (
        Tuple[RailsystemSchemas.Station, Dict[str, RailsystemSchemas.Line]] | None):
    now_msg_seq = kwargs.get('msg_seq', 1)
    next_msg_seq = now_msg_seq + 1
    railsystem: str = kwargs.get('r')
    group_id, user_id = get_group_and_user_id(message)
    logger.info(f'group_id: {group_id} user_id: {user_id}')
    station: List[Station] | Station = await get_station_by_keyword(station_name, railsystem)
    if not station:
        await message.reply(content=f'暂不支持 {station_name} 这个车站哦', msg_seq=next_msg_seq)
        return

    # a:查看全部结果 不过滤线网
    if not kwargs.get('a') and isinstance(station, list):
        railsystem_code_set = {_s.system_code for _s in station}
        if len(railsystem_code_set) > 1:
            # 如果有多个线网 则按照个性化配置默认线网去重
            _default_railsystem = await get_default_railsystem_code(group_id=group_id, user_id=user_id)
            logger.info(f'group_id:{group_id} user_id:{user_id} 默认线网:{_default_railsystem}')
            if _default_railsystem:
                filtered_stations = list(filter(lambda _s: _s.system_code == _default_railsystem, station))
                if not filtered_stations:
                    await message.reply(
                        msg_seq=next_msg_seq,
                        content=f'线网:{_default_railsystem} 没有 {station_name} 这个车站哦，可以加上"-a"在全部线网查找')
                    return
                if len(filtered_stations) == 1:
                    station = filtered_stations[0]
                else:
                    station = filtered_stations

    if isinstance(station, list):
        content: str = f'找到多个车站，要查看哪一个？\n'
        for s in station:
            content += f'{s.name} -r {s.system_code}\n'
        await message.reply(content=content, msg_seq=next_msg_seq)
        return

    _station: RailsystemSchemas.Station = await get_station_detail_byid(station.id)
    if not _station:
        await message.reply(content=f'获取车站:{station_name} 信息失败', msg_seq=next_msg_seq)
        return
    line_dict: Dict[str, RailsystemSchemas.Line] = {x.id: x for x in _station.lines}
    # 指定线路
    if (given_line_code := kwargs.get('l')) and isinstance(given_line_code, str):
        filtered_lines = list(filter(lambda x: x.code == given_line_code or x.name == given_line_code, _station.lines))
        if filtered_lines:
            line_dict: Dict[str, RailsystemSchemas.Line] = {x.id: x for x in filtered_lines}

    return _station, line_dict
