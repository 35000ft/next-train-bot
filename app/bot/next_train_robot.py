import botpy
from botpy import logging
from botpy.message import GroupMessage

from app.utils.AsyncLRUCache import AsyncLRUCache
from app.utils.command_utils import parse_command, find_context_command
from app.utils.common import dynamic_import
from app.utils.exceptions import exception_handler
from app.utils.qqbot_utils import get_group_and_user_id
from app.utils.security_utils import CodeManager

logger = logging.get_logger()


class NextTrainClient(botpy.Client):
    command_dict = {
        '实时': 'app.events.next_train_events.handle_get_station_realtime',
        '时刻表': 'app.events.next_train_events.handle_get_station_schedule',
        '票价': 'app.events.next_train_events.handle_query_price',
        '日票': 'app.events.next_train_events.handle_daily_ticket',
        '担当': 'app.events.cr_events.handle_query_emu_no',
        '推文': 'app.events.wechat_events.handle_query_wechat_article',
        '添加推文': 'app.events.wechat_events.handle_add_auto_reply_wechat_article',
        '报文': 'app.events.civil_aviation_events.handle_query_airport_weather_report',
        '雷达': 'app.events.cma_events.handle_query_radar',
        '注册': 'app.events.wechat_events.handle_register',
    }
    cache = AsyncLRUCache(maxsize=128)
    code_manager = CodeManager(ttl_seconds=60)

    # TODO
    async def send_help(self, message: GroupMessage, command_dict):
        all_command = [f'{i + 1}. {getattr(command_item[1], '__help') or command_item[0]}' for i, command_item in
                       enumerate(command_dict.items())]
        command_str = '\n'.join(all_command)
        return await message.reply(content=f'支持的指令如下:\n{command_str}')

    async def on_group_at_message_create(self, message: GroupMessage, command_dict: dict = None, **kwargs):
        if not command_dict:
            command_dict = self.command_dict
        try:
            command, params, argv = parse_command(message.content, accepted_commands=command_dict.keys())
            if command == '指令':
                return await self.send_help(message, command_dict)
            if handler_str := command_dict.get(command):
                handler = dynamic_import(handler_str)
                logger.info(f'command:{command} handler:{handler}')
                return await handler(message, *params, **argv, _bot=self, **kwargs)
            else:
                if message.content.isdigit():
                    # 尝试获取上下文
                    group_id, user_id = get_group_and_user_id(message)
                    try:
                        new_command = await find_context_command(user_id=user_id, group_id=group_id,
                                                                 option_str=message.content, cache=self.cache, **kwargs)
                    except:
                        return await self.send_help(message, command_dict)
                    logger.info(f"上下文指令:{new_command}")
                    message.content = new_command
                    return await self.on_group_at_message_create(message, **kwargs)
        except Exception as e:
            return await exception_handler(message, e)
