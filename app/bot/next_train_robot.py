import botpy
from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from app.events.civil_aviation_events import handle_query_flight, handle_query_airport_weather_report
from app.events.cma_events import handle_query_radar
from app.events.common_events import handle_fa, handle_wiki
from app.events.cr_events import handle_query_emu_no
from app.events.next_train_events import handle_get_station_realtime, handle_get_default_railsystem, handle_query_price
from app.events.next_train_events import handle_get_station_schedule, handle_daily_ticket, \
    handle_set_alias_station_name, \
    handle_get_station_realtime_alias_mode
from app.events.post_events import handle_post
from app.utils.AsyncLRUCache import AsyncLRUCache
from app.utils.command_utils import parse_command, find_context_command
from app.utils.exceptions import exception_handler
from app.utils.qqbot_utils import get_group_and_user_id

logger = logging.get_logger()


class NextTrainClient(botpy.Client):
    command_dict = {
        '实时': handle_get_station_realtime,
        '实时a': handle_get_station_realtime_alias_mode,
        '默认线网': handle_get_default_railsystem,
        '时刻表': handle_get_station_schedule,
        '票价': handle_query_price,
        '日票': handle_daily_ticket,
        '投稿': handle_post,
        '发': handle_fa,
        '担当': handle_query_emu_no,
        '机场大屏': handle_query_flight,
        '机场报文': handle_query_airport_weather_report,
        '报文': handle_query_airport_weather_report,
        '车站别名': handle_set_alias_station_name,
        # '喂鸡': handle_wiki,
        # 'wiki': handle_wiki,
        '雷达': handle_query_radar,
    }
    cache = AsyncLRUCache(maxsize=128)

    async def on_ready(self):
        logger.info(f"robot「{self.robot.name}」 on_ready!")

    async def on_c2c_message_create(self, message: C2CMessage):
        await message._api.post_c2c_message(
            openid=message.author.user_openid,
            msg_type=0, msg_id=message.id,
            content=f"我收到了你的消息：{message.content}"
        )

    async def on_group_at_message_create(self, message: GroupMessage) -> None:
        if message.content.strip() == '':
            await message.reply(content='确认存活，还没亖')
            return
        try:
            command, params, argv = parse_command(message.content, accepted_commands=self.command_dict.keys())
            if not command:
                await message.reply(content='目前不支持该指令哦~')
                return

            if handler := self.command_dict.get(command):
                await handler(message, *params, **argv, _bot=self)
            else:
                if message.content:
                    # 尝试获取上下文
                    group_id, user_id = get_group_and_user_id(message)
                    new_command = await find_context_command(user_id=user_id, group_id=group_id,
                                                             option_str=message.content, cache=self.cache)
                    logger.info(f"上下文指令:{new_command}")
                    message.content = new_command
                    await self.on_group_at_message_create(message)
                    return
                await message.reply(content='目前不支持该指令哦~')
        except Exception as e:
            await exception_handler(message, e)
