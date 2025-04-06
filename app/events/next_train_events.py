from typing import List, Dict, Tuple

from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from tabulate import tabulate

from app.events.common_events import handle_get_station_by_name
from app.events.daily_ticket_events import handle_njmtr_daily_ticket
from app.schemas import RailsystemSchemas
from app.schemas.RailsystemSchemas import TrainInfo
from app.service.file_service import cache_uploaded_file, get_cached_uploaded_file
from app.service.personaliz_service import get_default_railsystem_code, set_default_railsystem_code
from app.service.realtime_service import get_station_realtime, get_schedule_image
from app.utils import time_utils
from app.utils.command_utils import get_group_and_user_id
from app.utils.message_utils import post_group_base64_file
from app.utils.time_utils import get_now, end_of_date_timestamp
from app.service.ticket_price_service import query_ticket_price
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
    await message.reply(content=f'查询{station_name}实时列车中, 请稍后', msg_seq=1)
    r: Tuple[RailsystemSchemas.Station, Dict[str, RailsystemSchemas.Line]] = \
        await (handle_get_station_by_name(message, station_name, msg_seq=1, **kwargs))
    if not r:
        return
    station, line_dict = r
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


async def handle_get_station_schedule(message: GroupMessage | C2CMessage, station_name: str, line_code: str = None,
                                      **kwargs):
    await message.reply(content=f'查询{station_name}时刻表中, 请稍后', msg_seq=1)
    r: Tuple[RailsystemSchemas.Station, Dict[str, RailsystemSchemas.Line]] = \
        await (handle_get_station_by_name(message, station_name, msg_seq=1, **kwargs))
    if not r:
        return
    station, line_dict = r
    if len(line_dict) == 0:
        await message.reply(content=f'车站:{station.name} 暂无可查看的时刻表', msg_seq=2)
        return

    line_code = line_code.strip().strip('号线').upper() if line_code else None
    _temp_lines = list(filter(lambda x: x.code == line_code, line_dict.values())) if line_dict else []
    line = _temp_lines[0] if _temp_lines else None

    if not line and len(line_dict) > 1:
        content = f'车站:{station.name} 有多条线路，要查看哪一条？\n'
        for _line in line_dict.values():
            content += f"/时刻表 {station.name} {_line.code}\n"
        await message.reply(content=content, msg_seq=2)
        return
    if not line and len(line_dict) == 1:
        line = list(line_dict.values())[0]

    _date = get_now(get_offset_from_str(station.timezone))
    cache_key = f'schedule:{station.id}:{line.id}:{_date.strftime("%Y%m%d")}'
    if uploaded_file := await get_cached_uploaded_file(cache_key):
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=7,
            msg_id=message.id,
            media=uploaded_file,
            msg_seq=2,
        )
        return
    try:
        base64_data = await get_schedule_image(station.name, line.name, station_id=station.id, line_id=line.id,
                                               _date=_date)
    except Exception as e:
        logger.exception(e)
        await message.reply(content=f'获取车站:{station.name} 时刻表失败', msg_seq=2)
        return

    upload_media = await post_group_base64_file(
        _message=message,
        file_data=base64_data,
        group_openid=message.group_openid,
        file_type=1,  # 文件类型要对应上，具体支持的类型见方法说明
    )
    logger.info(f'上传成功:{upload_media}')
    # 资源上传后，会得到Media，用于发送消息
    await message._api.post_group_message(
        group_openid=message.group_openid,
        msg_type=7,
        msg_id=message.id,
        media=upload_media,
        msg_seq=2,
    )
    await cache_uploaded_file(cache_key, upload_media, expire_at=end_of_date_timestamp(_date))


async def handle_query_price(message: GroupMessage | C2CMessage, *station_names, **kwargs):
    if len(station_names) <= 1:
        await message.reply(content='至少要传入两个车站哦')
        return

    if len(station_names) == 2:
        return

    max_station_len = kwargs.get('max_station_len', 6)
    if len(station_names) > max_station_len:
        await message.reply(content=f"最多支持{max_station_len - 1}段行程哦")
        return
    all_stations = []
    total_price = 0
    for i in range(0, len(station_names) - 1):
        from_station_name = station_names[i]
        to_station_name = station_names[i + 1]
        from_r: Tuple[RailsystemSchemas.Station, Dict[str, RailsystemSchemas.Line]] = \
            await (handle_get_station_by_name(message, from_station_name, msg_seq=1))
        if not from_r:
            return

        to_r: Tuple[RailsystemSchemas.Station, Dict[str, RailsystemSchemas.Line]] = \
            await (handle_get_station_by_name(message, to_station_name, msg_seq=1))
        if not to_r:
            return

        to_station, _ = to_r
        from_station, _ = from_r

        all_stations.append(from_station)
        if i == len(station_names) - 2:
            all_stations.append(to_station)

        price = await query_ticket_price(from_station.railsystemCode, from_station.name, to_station.name)
        if price is not None:
            total_price += price
        else:
            await message.reply(content=f'找不到 {from_station.name}->{to_station.name} 的票价', msg_seq=2)
            return
    content = f'{"->".join([x.name for x in all_stations])} 票价为:{total_price}元'
    await message.reply(content=content, msg_seq=2)


async def handle_daily_ticket(message: GroupMessage | C2CMessage, station_name: str, **kwargs):
    r: Tuple[RailsystemSchemas.Station, Dict[str, RailsystemSchemas.Line]] = \
        await (handle_get_station_by_name(message, station_name, msg_seq=1, **kwargs))
    if not r:
        return
    station, line_dict = r
    railsystem_code = station.railsystemCode
    if railsystem_code == 'NJMTR':
        return await handle_njmtr_daily_ticket(message, station, **kwargs)
    else:
        await message.reply(content=f'线网:{railsystem_code} 不支持日票哦')
