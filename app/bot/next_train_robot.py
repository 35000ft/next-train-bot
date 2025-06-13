import botpy
from botpy import logging
from botpy.message import GroupMessage

from app.events.civil_aviation_events import handle_query_airport_weather_report
from app.events.cma_events import handle_query_radar
from app.events.cr_events import handle_query_emu_no
from app.events.next_train_events import handle_get_station_realtime, handle_query_price
from app.events.next_train_events import handle_get_station_schedule, handle_daily_ticket
from app.utils.AsyncLRUCache import AsyncLRUCache
from app.utils.command_utils import parse_command, find_context_command
from app.utils.exceptions import exception_handler
from app.utils.qqbot_utils import get_group_and_user_id
from app.utils.security_utils import CodeManager

logger = logging.get_logger()


class NextTrainClient(botpy.Client):
    command_dict = {
        '实时': handle_get_station_realtime,
        '时刻表': handle_get_station_schedule,
        '票价': handle_query_price,
        '日票': handle_daily_ticket,
        '担当': handle_query_emu_no,
        # '机场大屏': handle_query_flight,
        '报文': handle_query_airport_weather_report,
        '雷达': handle_query_radar,
    }
    cache = AsyncLRUCache(maxsize=128)
    code_manager = CodeManager(ttl_seconds=60)

    async def send_help(self, message: GroupMessage):
        all_command = [f'{i + 1}. {getattr(command_item[1], '__help') or command_item[0]}' for i, command_item in
                       enumerate(self.command_dict.items())]
        command_str = '\n'.join(all_command)
        return await message.reply(content=f'支持的指令如下:\n{command_str}')

    async def on_group_at_message_create(self, message: GroupMessage, **kwargs):
        try:
            command, params, argv = parse_command(message.content, accepted_commands=self.command_dict.keys())
            if command == '指令':
                return await self.send_help(message)
            if handler := self.command_dict.get(command):
                return await handler(message, *params, **argv, _bot=self, **kwargs)
            else:
                if message.content.isdigit():
                    # 尝试获取上下文
                    group_id, user_id = get_group_and_user_id(message)
                    try:
                        new_command = await find_context_command(user_id=user_id, group_id=group_id,
                                                                 option_str=message.content, cache=self.cache, **kwargs)
                    except:
                        return await self.send_help(message)
                    logger.info(f"上下文指令:{new_command}")
                    message.content = new_command
                    return await self.on_group_at_message_create(message, **kwargs)
        except Exception as e:
            return await exception_handler(message, e)
