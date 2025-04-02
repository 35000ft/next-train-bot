from datetime import datetime
from typing import List, Dict

from botpy import logging
from botpy.message import GroupMessage, C2CMessage
import wcwidth
from app.models.Railsystem import Station
from app.schemas import RailsystemSchemas
from app.schemas.RailsystemSchemas import TrainInfo
from app.service.personaliz_service import get_default_railsystem_code, set_default_railsystem_code
from app.service.railsystem_service import get_station_by_names, get_station_detail_byid, get_station_by_keyword
from tabulate import tabulate

from app.service.realtime_service import get_station_realtime
from app.utils import time_utils
from app.utils.command_utils import get_group_and_user_id
from app.utils.time_utils import get_offset_from_str

logger = logging.get_logger()


def filter_latest_train_for_each_terminal(train_info_list: List[TrainInfo], **kwargs) -> List[TrainInfo]:
    """
    按 terminal 分组，每组中选择 dep 最近且在当前时间之后的记录。
    """
    # 获取当前时间
    now = time_utils.get_now(get_offset_from_str(kwargs['timezone']))
    if not train_info_list:
        return []
    # 按 terminal 分组
    grouped_by_terminal = {}
    for train_info in train_info_list:
        terminal = train_info.terminal
        if terminal not in grouped_by_terminal:
            grouped_by_terminal[terminal] = []
        grouped_by_terminal[terminal].append(train_info)

    # 在每组中筛选符合条件的记录
    result = []
    for terminal, group in grouped_by_terminal.items():
        # 筛选出 dep 在当前时间之后的记录
        valid_trains = [train for train in group if train.dep > now]
        if valid_trains:
            # 按 dep 排序，取最近的记录
            valid_trains.sort(key=lambda x: x.dep)
            result.append(valid_trains[0])

    return result


async def handle_get_station_realtime(message: GroupMessage | C2CMessage, station_name: str, **kwargs):
    railsystem: str = kwargs.get('r')
    logger.info(f'handle_get_station_realtime: {message.content} {station_name} {railsystem}')
    group_id, user_id = get_group_and_user_id(message)
    logger.info(f'group_id: {group_id} user_id: {user_id}')
    station: List[Station] | Station = await get_station_by_keyword(station_name, railsystem)
    if not station:
        await message.reply(content=f'暂不支持 {station_name} 这个车站哦')
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
                        content=f'线网:{_default_railsystem} 没有 {station_name} 这个车站哦，可以加上"-a"在全部线网查找')
                    return
                if len(filtered_stations) == 1:
                    station = filtered_stations[0]
                else:
                    station = filtered_stations

    if isinstance(station, list):
        content: str = f'找到多个车站，要查看哪一个？\n'
        for s in station:
            content += f'/实时 {s.name} -r {s.system_code}\n'
        await message.reply(content=content)
        return

    await message.reply(content=f'查询{station.name}实时列车中, 请稍后', msg_seq=1)
    station: RailsystemSchemas.Station = await get_station_detail_byid(station.id)
    if not station:
        await message.reply(content=f'获取车站:{station_name} 信息失败', msg_seq=2)
        return
    line_dict: [str, RailsystemSchemas.Line] = {x.id: x for x in station.lines}
    # 指定线路
    if (given_line_code := kwargs.get('l')) and isinstance(given_line_code, str):
        filtered_lines = list(filter(lambda x: x.code == given_line_code or x.name == given_line_code, station.lines))
        if filtered_lines:
            line_dict: [str, RailsystemSchemas.Line] = {x.id: x for x in filtered_lines}

    train_info_dict: Dict[str, List[TrainInfo]] = await get_station_realtime(station.id,
                                                                             line_ids=list(line_dict.keys()))
    if not train_info_dict:
        await message.reply(content=f'获取 {station_name} 实时列车失败', msg_seq=2)
        return
    content = f'车站:{station_name} 实时列车 更新于:{time_utils.get_now(get_offset_from_str(station.timezone)).strftime("%H:%M:%S")}\n'

    for line_id, train_info_list in train_info_dict.items():
        line = line_dict.get(line_id)
        if line:
            content += f'{line.name}:\n'
            _train_list = filter_latest_train_for_each_terminal(train_info_list, timezone=station.timezone)
            if not _train_list:
                content += '    暂无列车\n'
                continue

            headers = ['终点站', '出发时刻', '类型']
            table = [[train_info.terminal, train_info.dep.strftime('%H:%M'), train_info.trainType] for train_info in
                     _train_list]
            content += tabulate(table, headers, tablefmt='simple')
            content += '\n'
    await message.reply(content=content, msg_seq=2)


async def handle_get_default_railsystem(message: GroupMessage | C2CMessage, railsystem_to_set: str = None, **kwargs):
    group_id, user_id = get_group_and_user_id(message)
    default_railsystem_code = await get_default_railsystem_code(group_id=group_id, user_id=user_id)

    if not railsystem_to_set:
        if default_railsystem_code:
            await message.reply(content=f'你的默认线网为:{default_railsystem_code}')
        else:
            await message.reply(content='你当前没有设置默认线网哦')
        return

    if kwargs.get('g'):
        await set_default_railsystem_code(group_id=None, user_id=user_id, railsystem_code=railsystem_to_set)
    else:
        await set_default_railsystem_code(group_id=group_id, user_id=user_id, railsystem_code=railsystem_to_set)
    if group_id:
        await message.reply(content=f'设置默认线网成功，只会在本群对你生效, 如需全局生效请加"-g"')
    else:
        await message.reply(content=f'设置默认线网成功，当前你的默认线网:{railsystem_to_set}')
