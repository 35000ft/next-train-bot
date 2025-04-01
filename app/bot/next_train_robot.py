import botpy
from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.events.next_train_events import handle_get_station_realtime
from app.utils.command_utils import parse_command

_log = logging.get_logger()


class NextTrainClient(botpy.Client):
    command_dict = {
        '实时': handle_get_station_realtime
    }

    async def on_ready(self):
        _log.info(f"robot「{self.robot.name}」 on_ready!")

    async def on_c2c_message_create(self, message: C2CMessage):
        await message._api.post_c2c_message(
            openid=message.author.user_openid,
            msg_type=0, msg_id=message.id,
            content=f"我收到了你的消息：{message.content}"
        )

    async def on_group_at_message_create(self, message: GroupMessage) -> None:
        command, args = parse_command(message.content)
        if not command:
            await message.reply(content='目前不支持该指令哦~')
            return

        if handler := self.command_dict.get(command):
            await handler(message, *args)
            # await message.reply(content=f'bot收到了消息: 指令:{command} 参数:{args}')
        else:
            await message.reply(content='目前不支持该指令哦~')
