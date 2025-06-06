import hashlib
import logging
import os
import time
from typing import Optional

from botpy.message import GroupMessage
from fastapi import FastAPI, Query
from fastapi.requests import Request
from fastapi.responses import Response

from app.schemas.weixin import ReceiveMsgBody, ResponseMsgBody
from app.utils.command_utils import parse_command, find_context_command
from app.utils.common import WechatMessage
from app.utils.exceptions import exception_handler
from app.utils.qqbot_utils import get_group_and_user_id

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WECHAT_TOKEN = os.getenv('WECHAT_TOKEN')
WECHAT_ID = os.getenv('WECHAT_ID')


@app.get("/")
def check_signature(
        signature: str = Query(...),
        timestamp: str = Query(...),
        nonce: str = Query(...),
        echostr: Optional[str] = Query(None)
):
    logger.info(f"signature = {signature}")
    logger.info(f"timestamp = {timestamp}")
    logger.info(f"nonce = {nonce}")
    logger.info(f"echostr = {echostr}")

    # 第一步：自然排序
    tmp = sorted([WECHAT_TOKEN, timestamp, nonce])

    # 第二步：sha1 加密
    source_str = ''.join(tmp)
    local_signature = hashlib.sha1(source_str.encode('utf-8')).hexdigest()
    logger.info(f'signature:{signature} local_signature:{local_signature}')
    # 第三步：验证签名
    if signature == local_signature:
        logger.info('validate signature ok')
        return Response(content=echostr or "", media_type="text/plain")
    return None


@app.post("/")
async def handle_receive_msg(request: Request):
    # 读取原始 XML 数据
    body_bytes = await request.body()
    xml_str = body_bytes.decode("utf-8")

    try:
        msg = ReceiveMsgBody.from_xml(xml_str)
    except Exception as e:
        return Response(content="Invalid Message Format", status_code=422)
    logger.debug(f'receive msg:{msg.Content} from:{msg.FromUserName}')

    message = WechatMessage(msg.FromUserName, {'group_openid': WECHAT_ID, 'to_username': msg.ToUserName})
    resp = await message.reply()

    return Response(content=resp.to_xml(), media_type="application/xml; charset=UTF-8")
