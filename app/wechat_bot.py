import hashlib
from typing import Optional

import botpy
from botpy import logging
from fastapi import FastAPI, Query
from fastapi.requests import Request
from fastapi.responses import Response

from app.bot.next_train_robot import NextTrainClient
from app.config import get_db_session
from app.models.auth import BotUser
from app.schemas.wechat import ReceiveMsgBody, ResponseMsgBody
from app.service.user_service import query_user
from app.utils.common import WechatMessage
from app.utils.wechat_utils import load_account_info

logger = logging.get_logger()

app = FastAPI()

intents = botpy.Intents(public_messages=True)
bot_instance = NextTrainClient(intents=intents, is_sandbox=True)


@app.get("/")
async def check_signature(
        signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
        echostr: Optional[str] = Query(None),
        account: str = Query(...)
):
    account_info = load_account_info(account)
    # 第一步：自然排序
    tmp = sorted([account_info.get('wechat_token'), timestamp, nonce])

    # 第二步：sha1 加密
    source_str = ''.join(tmp)
    local_signature = hashlib.sha1(source_str.encode('utf-8')).hexdigest()
    # 第三步：验证签名
    if signature == local_signature:
        return Response(content=echostr or "", media_type="text/plain")
    return None


@app.post("/")
async def handle_receive_msg(request: Request, account: str = Query(...)):
    account_info = load_account_info(account)
    body_bytes = await request.body()
    xml_str = body_bytes.decode("utf-8")

    try:
        msg = ReceiveMsgBody.from_xml(xml_str)
    except Exception as e:
        logger.warning(f'Invalid message:{xml_str}', exc_info=e)
        return Response(content="Invalid Message Format", status_code=422)

    message = WechatMessage(msg.FromUserName, {'group_openid': account_info['wechat_id'],
                                               'to_username': msg.ToUserName, 'content': msg.Content})
    async with get_db_session() as session:
        bot_user: BotUser = await query_user(session, account=msg.FromUserName)
        if bot_user:
            message.bot_user = bot_user

    resp: ResponseMsgBody = await bot_instance.on_group_at_message_create(message, account=account_info)
    logger.info(f'response:{resp.to_xml()}')
    return Response(content=resp.to_xml(), media_type="application/xml; charset=UTF-8")
