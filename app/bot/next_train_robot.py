import botpy
from botpy import logging
from botpy.message import GroupMessage

from app.events.civil_aviation_events import handle_query_flight, handle_query_airport_weather_report
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
        '机场大屏': handle_query_flight,
        '机场报文': handle_query_airport_weather_report,
        '报文': handle_query_airport_weather_report,
        '雷达': handle_query_radar,
    }
    cache = AsyncLRUCache(maxsize=128)
    code_manager = CodeManager(ttl_seconds=60)

    async def on_group_at_message_create(self, message: GroupMessage) -> None:
        all_command = [f'{i + 1}. {c}' for i, c in enumerate(self.command_dict.keys())]
        command_str = '\n'.join(all_command)
        logger.info(f'receive msg:{message.content}')
        try:
            command, params, argv = parse_command(message.content, accepted_commands=self.command_dict.keys())
            if not command:
                return await message.reply(content=f'请输入合法的指令:\n{command_str}')
            if handler := self.command_dict.get(command):
                return await handler(message, *params, **argv, _bot=self)
            else:
                if message.content:
                    # 尝试获取上下文
                    group_id, user_id = get_group_and_user_id(message)
                    new_command = await find_context_command(user_id=user_id, group_id=group_id,
                                                             option_str=message.content, cache=self.cache)
                    logger.info(f"上下文指令:{new_command}")
                    message.content = new_command
                    return await self.on_group_at_message_create(message)
                return await message.reply(content=f'请输入合法的指令:\n{command_str}')
        except Exception as e:
            return await exception_handler(message, e)
