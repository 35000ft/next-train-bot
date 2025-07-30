import random
from typing import List, Dict, Tuple

from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from wikipedia import wikipedia, PageError

from app.config import accepted_wiki_topics
from app.events.aunu_events import get_star_party, handle_get_apod
from app.models.Railsystem import Station
from app.schemas import railsystem
from app.service.personalize_service import get_default_railsystem_code
from app.service.railsystem_service import get_station_detail_byid, get_station_by_keyword
from app.utils.command_utils import save_context_command
from app.utils.exceptions import BusinessException
from app.utils.forbidden_words import check_params_contains_forbidden_word, replace_forbidden_word
from app.utils.qqbot_utils import get_group_and_user_id

logger = logging.get_logger()


async def handle_get_station_by_name(message: GroupMessage | C2CMessage, station_name: str, **kwargs) -> (
        Tuple[railsystem.Station, Dict[str, railsystem.Line]] | None):
    now_msg_seq = kwargs.get('msg_seq', 1)
    next_msg_seq = now_msg_seq + 1
    _railsystem: str = kwargs.get('r')
    group_id, user_id = get_group_and_user_id(message)
    logger.info(f'group_id: {group_id} user_id: {user_id}')
    station: List[Station] | Station = await get_station_by_keyword(station_name, _railsystem)
    if not station:
        raise BusinessException(
            f'暂不支持 {station_name} 这个车站哦。如已设置别名，请通过以下指令查询:\n/{kwargs.get("command_name", "<指令名>")}a {station_name}')

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
        _command_name = kwargs.get("command_name")
        if _command_name:
            option_str = await save_context_command(user_id=user_id, group_id=group_id, cache=kwargs.get('_bot').cache,
                                                    command_list=[
                                                        f'/{_command_name} {s.name} -r {s.system_code}\n' for s
                                                        in station], )
            raise BusinessException(content + option_str)

    _station: railsystem.Station = await get_station_detail_byid(station.id)
    if not _station:
        await message.reply(content=f'获取车站:{station_name} 信息失败', msg_seq=next_msg_seq)
        return
    line_dict: Dict[str, railsystem.Line] = {x.id: x for x in _station.lines}
    # 指定线路
    if (given_line_code := kwargs.get('l')) and isinstance(given_line_code, str):
        filtered_lines = list(
            filter(lambda x: x.code == given_line_code or x.name == given_line_code, _station.lines))
        if filtered_lines:
            line_dict: Dict[str, railsystem.Line] = {x.id: x for x in filtered_lines}

    return _station, line_dict


async def handle_fa(message: GroupMessage | C2CMessage, *args, **kwargs):
    if not args:
        empty_contents = ['发null', '发，发什么发', '发undefined', '发nil', '发NaN', '发疒']
        await message.reply(content=random.choice(empty_contents), msg_seq=1)
        return

    fa_type = args[0]
    accepted_type = {
        'starparty': get_star_party,
        'apod': handle_get_apod
    }
    _handle_func = accepted_type[fa_type]
    await _handle_func(message, *args[1:], **kwargs)


@check_params_contains_forbidden_word("keyword")
async def handle_get_wiki_summary(message: GroupMessage | C2CMessage, keyword: str, **kwargs):
    keyword = keyword.strip()
    if not keyword:
        await message.reply(content='不知道你想查什么')
        return
    max_word = 400
    lang = kwargs.get('l', 'zh')
    wikipedia.set_lang(lang)

    try:
        page = wikipedia.page(keyword)
    except PageError as e:
        search_result_words = wikipedia.search(keyword)
        if search_result_words:
            page = wikipedia.page(search_result_words[0])
        else:
            await message.reply(content=f'没有找到任何关于"{keyword}"的内容 使用语言:{lang}')
            return
    for category in page.categories:
        for topic in accepted_wiki_topics:
            if topic in category:
                wiki_content = page.summary
                if wiki_content:
                    wiki_content = replace_forbidden_word(wiki_content)
                    await message.reply(content=wiki_content[0:max_word])
                    return
    await message.reply(content='这是不能触碰的滑梯')
