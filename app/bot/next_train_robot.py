import re
import uuid

import botpy
from botpy import logging
from botpy.message import GroupMessage, C2CMessage

from app.utils.AsyncLRUCache import AsyncLRUCache
from app.utils.dify_client import chat_stream_enhanced
from app.utils.qqbot_utils import get_group_and_user_id
from app.utils.security_utils import CodeManager

logger = logging.get_logger()


class NextTrainClient(botpy.Client):
    cache = AsyncLRUCache(maxsize=128)
    code_manager = CodeManager(ttl_seconds=60)
    # user_key -> conversation_id, TTL 1 hour
    _dify_conversations = AsyncLRUCache(maxsize=1024, ttl_seconds=3600)

    LOCAL_COMMANDS = {
        '清除上下文': '_cmd_clear_context',
        '清除': '_cmd_clear_context',
        'clear': '_cmd_clear_context',
        'reset': '_cmd_clear_context',
        '对话id': '_cmd_show_conversation_id',
        'cid': '_cmd_show_conversation_id',
    }

    async def on_ready(self):
        logger.info(f"robot「{self.robot.name}」 on_ready!")

    async def on_c2c_message_create(self, message: C2CMessage):
        await self._handle_dify_chat(message)

    async def on_group_at_message_create(self, message: GroupMessage) -> None:
        await self._handle_dify_chat(message)

    async def _cmd_clear_context(self, message: GroupMessage | C2CMessage):
        group_id, user_id = get_group_and_user_id(message)
        user_key = f"{user_id}:{group_id}"
        await self._dify_conversations.delete(user_key)
        await message.reply(content='上下文已清除', msg_seq=1)

    async def _cmd_show_conversation_id(self, message: GroupMessage | C2CMessage):
        group_id, user_id = get_group_and_user_id(message)
        user_key = f"{user_id}:{group_id}"
        conversation_id = await self._dify_conversations.get(user_key)
        if conversation_id:
            await message.reply(content=f'当前对话ID: {conversation_id}', msg_seq=1)
        else:
            await message.reply(content='当前没有对话ID', msg_seq=1)

    async def _handle_dify_chat(self, message: GroupMessage | C2CMessage):
        group_id, user_id = get_group_and_user_id(message)
        user_key = f"{user_id}:{group_id}"
        content = self._clean_content(message.content)
        if not content:
            await message.reply(content='确认存活，还没亖')
            return

        # 本地命令拦截
        if content in self.LOCAL_COMMANDS:
            handler_name = self.LOCAL_COMMANDS[content]
            handler = getattr(self, handler_name)
            await handler(message)
            return

        conversation_id = await self._dify_conversations.get(user_key)
        text_buffer = ""
        think_buffer = ""
        in_think = False
        new_conversation_id: str | None = None
        await message.reply(content='收到, 正在处理中', )
        msg_seq = 2

        def _append_text(new_text: str):
            nonlocal text_buffer, think_buffer, in_think
            if in_think:
                think_buffer += new_text
                if '</think>' in think_buffer:
                    end = think_buffer.find('</think>') + len('</think>')
                    text_buffer += think_buffer[end:]
                    think_buffer = ""
                    in_think = False
            else:
                text_buffer += new_text
                if '<think>' in text_buffer:
                    idx = text_buffer.find('<think>')
                    think_buffer = text_buffer[idx:]
                    text_buffer = text_buffer[:idx]
                    in_think = True
                    if '</think>' in think_buffer:
                        end = think_buffer.find('</think>') + len('</think>')
                        text_buffer += think_buffer[end:]
                        think_buffer = ""
                        in_think = False

        try:
            async for event in chat_stream_enhanced(
                    query=content,
                    conversation_id=conversation_id,
                    user_id=user_key,
            ):
                if msg_seq > 5:
                    logger.warning(f"exceed max msg seq, {conversation_id=}")
                    break
                if event.conversation_id:
                    new_conversation_id = event.conversation_id

                if event.event_type == "text":
                    _append_text(event.text)
                    while True:
                        to_send, text_buffer = self._try_flush_text(text_buffer, min_len=500)
                        if not to_send:
                            break
                        await message.reply(content=to_send, msg_seq=msg_seq)
                        msg_seq += 1

                elif event.event_type == "error":
                    if text_buffer.strip():
                        await message.reply(content=text_buffer.strip(), msg_seq=msg_seq)
                        msg_seq += 1
                    trace = uuid.uuid4().hex
                    logger.error(f'dify response error:{event.text} {event.conversation_id=} {trace=}')
                    await message.reply(content=f'发送错误, Trace:{trace}', msg_seq=msg_seq)
                    return

            if new_conversation_id:
                await self._dify_conversations.set(user_key, new_conversation_id)

            # 结束响应，发送剩余文本（丢弃未闭合的think内容）
            if text_buffer.strip():
                await message.reply(content=text_buffer.strip(), msg_seq=msg_seq)
                msg_seq += 1

            if msg_seq == 2:
                await message.reply(content='没有收到回复哦~', msg_seq=msg_seq)

        except Exception as e:
            logger.exception(f"Dify chat error: {e}")
            if text_buffer.strip():
                await message.reply(content=text_buffer.strip(), msg_seq=msg_seq)
                msg_seq += 1
            await message.reply(content='对话出错了，请稍后重试', msg_seq=msg_seq)

    @staticmethod
    def _try_flush_text(buffer: str, min_len: int = 100) -> tuple[str, str]:
        if len(buffer) <= min_len:
            return "", buffer
        last_punct = -1
        for i, ch in enumerate(buffer):
            if ch in '。!':
                last_punct = i
        if last_punct >= min_len:
            return buffer[:last_punct + 1], buffer[last_punct + 1:]
        return "", buffer

    @staticmethod
    def _clean_content(content: str | None) -> str:
        if not content:
            return ''
        # 去除 QQ @ 提及，如 <@!123456> 或 <@123456>
        cleaned = re.sub(r'<@!?\d+>', '', content)
        return cleaned.strip()
