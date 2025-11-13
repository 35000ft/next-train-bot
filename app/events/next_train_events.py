import os
from typing import List, Dict, Tuple

from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from tabulate import tabulate

from app.events.common_events import handle_get_station_by_name
from app.events.daily_ticket_events import handle_njmtr_daily_ticket
from app.schemas import railsystem
from app.schemas.railsystem import TrainInfo
from app.service.file_service import get_cached_uploaded_file
from app.service.realtime_service import get_station_realtime, get_schedule_image
from app.service.ticket_price_service import query_ticket_price
from app.utils import time_utils
from app.utils.command_utils import save_context_command
from app.utils.common import command_wrapper
from app.utils.exceptions import InputException
from app.utils.qqbot_utils import get_group_and_user_id
from app.utils.time_utils import get_now
from app.utils.time_utils import get_offset_from_str
from app.utils.wechat_utils import upload_media

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


async def handle_get_station_realtime_core(message, station: railsystem.Station,
                                           line_dict: Dict[str, railsystem.Line]):
    train_info_dict: Dict[str, List[TrainInfo]] = await get_station_realtime(station.id,
                                                                             line_ids=list(line_dict.keys()))
    if not train_info_dict:
        return await message.reply(content=f'获取 {station.name} 实时列车失败')
    content = f'车站:{station.name} 实时列车 更新于:{time_utils.get_now(get_offset_from_str(station.timezone)).strftime("%H:%M:%S")}\n'

    for line_id, train_info_list in train_info_dict.items():
        line = line_dict.get(line_id)
        if line:
            content += f"""<a href='{os.getenv("NEXT_TRAIN_PAGE_BASEURL")}/station/schedule/{station.id}/{line.id}'>{line.name}</a>:\n"""
            _train_list = filter_latest_train_for_each_terminal(train_info_list, timezone=station.timezone)
            if not _train_list:
                content += '    暂无列车\n'
                continue

            headers = ['终点站', '出发时刻', '类型']
            table = [
                [
                    train_info.terminal,
                    train_info.dep.strftime('%H:%M') if not train_info.isLastStop
                    else train_info.arr.strftime('%H:%M'),
                    train_info.trainType if not train_info.isLastStop else '终到'
                ]
                for train_info in _train_list]
            content += tabulate(table, headers, tablefmt='simple')

            content += '\n'
    content += f"<a href='{os.getenv("NEXT_TRAIN_PAGE_BASEURL")}/station/{station.id}'>点此查看详情</a>"
    return await message.reply(content=content, msg_seq=2)


@command_wrapper(help='实时 新街口')
async def handle_get_station_realtime(message: GroupMessage | C2CMessage, station_name: str, **kwargs):
    r: Tuple[railsystem.Station, Dict[str, railsystem.Line]] = \
        await (handle_get_station_by_name(message, station_name, command_name='实时', **kwargs))
    station, line_dict = r
    return await handle_get_station_realtime_core(message, station, line_dict)


@command_wrapper(help='时刻表 新街口 2(可选, 指定线路)')
async def handle_get_station_schedule(message: GroupMessage | C2CMessage, station_name: str, line_code: str = None,
                                      **kwargs):
    # 设置默认线网
    group_id, user_id = get_group_and_user_id(message)
    r: Tuple[railsystem.Station, Dict[str, railsystem.Line]] = \
        await (handle_get_station_by_name(message, station_name, command_name='时刻表', **kwargs))
    station, line_dict = r
    if len(line_dict) == 0:
        return await message.reply(content=f'车站:{station.name} 暂无可查看的时刻表', msg_seq=2)

    line_code = line_code.strip().strip('号线').upper() if line_code else None
    _temp_lines = list(filter(lambda x: x.code == line_code, line_dict.values())) if line_dict else []
    line = _temp_lines[0] if _temp_lines else None

    if not line and len(line_dict) > 1:
        content = f'车站:{station.name} 有多条线路，要查看哪一条？（回复序号即可）\n'
        option_str = await save_context_command(user_id=user_id, group_id=group_id, cache=kwargs.get('_bot').cache,
                                                command_list=[f"时刻表 {station.name} {_line.code}" for _line in
                                                              line_dict.values()], )
        return await message.reply(content=content + option_str)
    if not line and len(line_dict) == 1:
        line = list(line_dict.values())[0]

    _date = get_now(get_offset_from_str(station.timezone))
    cache_key = f'schedule:{station.id}:{line.id}:{_date.strftime("%Y%m%d")}'
    if uploaded_file := await get_cached_uploaded_file(cache_key):
        return await message.reply(media_info=uploaded_file)
    try:
        filepath = await get_schedule_image(station.name, line.name, station_id=station.id, line_id=line.id,
                                            _date=_date)
    except Exception as e:
        logger.exception(e)
        return await message.reply(content=f'获取车站:{station.name} 时刻表失败')

    media_info = await upload_media(media_type='image', media_path=filepath, **kwargs)
    return await message.reply(media=media_info, content=f'{station.name}-{line.name} 时刻表')


@command_wrapper(help='票价 新街口 南京南站 [更多车站...]')
async def handle_query_price(message: GroupMessage | C2CMessage, *station_names, **kwargs):
    if len(station_names) <= 1:
        raise InputException('至少要传入两个车站哦')

    max_station_len = kwargs.get('max_station_len', 6)
    if len(station_names) > max_station_len:
        raise InputException(f"最多支持{max_station_len - 1}段行程哦")
    all_stations = []
    total_price = 0
    for i in range(0, len(station_names) - 1):
        from_station_name = station_names[i]
        to_station_name = station_names[i + 1]
        from_r: Tuple[railsystem.Station, Dict[str, railsystem.Line]] = \
            await (handle_get_station_by_name(message, from_station_name, command_name='票价', msg_seq=1, **kwargs))

        to_r: Tuple[railsystem.Station, Dict[str, railsystem.Line]] = \
            await (handle_get_station_by_name(message, to_station_name, command_name='票价', msg_seq=1, **kwargs))

        to_station, _ = to_r
        from_station, _ = from_r

        all_stations.append(from_station)
        if i == len(station_names) - 2:
            all_stations.append(to_station)

        price = await query_ticket_price(from_station.railsystemCode, from_station.name, to_station.name)
        if price is not None:
            total_price += price
        else:
            return await message.reply(content=f'找不到 {from_station.name}->{to_station.name} 的票价', msg_seq=2)

    content = f'{"->".join([x.name for x in all_stations])} 票价为:{total_price}元'
    return await message.reply(content=content, msg_seq=2)


@command_wrapper(help='日票 高淳')
async def handle_daily_ticket(message: GroupMessage | C2CMessage, station_name: str, **kwargs):
    r: Tuple[railsystem.Station, Dict[str, railsystem.Line]] = \
        await (handle_get_station_by_name(message, station_name, command_name='日票', msg_seq=1, **kwargs))
    station, line_dict = r
    railsystem_code = station.railsystemCode
    if railsystem_code == 'NJMTR':
        return await handle_njmtr_daily_ticket(message, station, **kwargs)
    else:
        return await message.reply(content=f'线网:{railsystem_code} 不支持日票哦')
