from datetime import datetime
from typing import List, Dict

import pytz
from botpy.message import GroupMessage, C2CMessage
import wcwidth
from app.models.Railsystem import Station
from app.schemas import RailsystemSchemas
from app.schemas.RailsystemSchemas import TrainInfo
from app.service.railsystem_service import get_station_by_names, get_station_detail_byid
from tabulate import tabulate
from logging import getLogger

from app.service.realtime_service import get_station_realtime
from app.utils import time_utils

logger = getLogger(__name__)


def filter_latest_train_for_each_terminal(train_info_list: List[TrainInfo], **kwargs) -> List[TrainInfo]:
    """
    按 terminal 分组，每组中选择 dep 最近且在当前时间之后的记录。
    """
    # 获取当前时间
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
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


async def handle_get_station_realtime(message: GroupMessage | C2CMessage, station_name: str, railsystem: str = None):
    logger.debug(f'handle_get_station_realtime: {message.content} {station_name} {railsystem}')
    stations = await get_station_by_names([station_name], railsystem)
    station: List[Station] | Station = stations[station_name]
    if not station:
        await message.reply(content=f'暂不支持 {station_name} 这个车站哦')
        return

    if isinstance(station, list):
        railsystem_codes = [x.system_code for x in station]
        content: str = f'找到多个同名车站，要查看哪一个？\n'
        for railsystem_code in railsystem_codes:
            content += f'/实时 {station_name} {railsystem_code}\n'
        await message.reply(content=content)
        return
    await message.reply(content=f'查询{station_name}实时列车中, 请稍后', msg_seq=1)
    station: RailsystemSchemas.Station = await get_station_detail_byid(station.id)
    if not station:
        return message.reply(content=f'获取车站:{station_name} 信息失败,请稍后再试')

    line_dict: [str, RailsystemSchemas.Line] = {x.id: x for x in station.lines}
    train_info_dict: Dict[str, List[TrainInfo]] = await get_station_realtime(station.id,
                                                                             line_ids=list(line_dict.keys()))
    if not train_info_dict:
        await message.reply(content=f'获取 {station_name} 实时列车失败')
        return
    content = f'车站:{station_name} 实时列车 更新于:{datetime.now().strftime("%H:%M:%S")}\n'

    for line_id, train_info_list in train_info_dict.items():
        line = line_dict.get(line_id)
        if line:
            content += f'{line.name}:\n'
            _train_list = filter_latest_train_for_each_terminal(train_info_list)
            if not _train_list:
                content += '    暂无列车\n'
                continue

            headers = ['终点站', '出发时刻', '类型']
            table = [[train_info.terminal, train_info.dep.strftime('%H:%M'), train_info.trainType] for train_info in
                     _train_list]
            content += tabulate(table, headers, tablefmt='simple')
            content += '\n'
    await message.reply(content=content, msg_seq=2)
