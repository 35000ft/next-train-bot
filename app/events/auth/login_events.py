import hashlib
import hmac
import os
import time
import urllib.parse
import uuid

import httpx
from botpy import logging
from botpy.message import GroupMessage

logger = logging.get_logger()


async def handle_signup_login(message: GroupMessage, authorization_code: str, username: str = None, email: str = None,
                              phone: str = None,
                              **kwargs):
    account = kwargs.get('account')
    if not username:
        username = f'botu_{uuid.uuid4()}'
    userid = message.author.member_openid
    logger.info(f'Login Next Train: user openid:{userid}')
    group_id = account['wechat_id']
    platform = 'wechat'
    async with httpx.AsyncClient(timeout=120) as client:
        url = f'{os.getenv("REALTIME_API_BASEURL")}/users/bot-login'
        timestamp = int(time.time())
        data_str: str = f'{userid}@{group_id}@{platform}@{authorization_code}'
        client_key = account.get('next_train_client_key')
        sign = hmac.new(client_key.encode('utf-8'), data_str.encode('utf-8'), hashlib.sha256).hexdigest()
        resp = await client.post(url, json={
            'username': username,
            'groupId': group_id,
            'userId': userid,
            'platform': platform,
            'email': email,
            'phone': phone,
            'sign': sign,
            'authentication': authorization_code,
        })
        try:
            resp.raise_for_status()
        except Exception as e:
            logger.exception('请求Next Train第三方登录失败', exc_info=e)
            return await message.reply(content='请求登录失败')
        j_obj: dict = resp.json()
        if not (failed := j_obj.get('data').get("failed")):
            return await message.reply(content=f'登录成功，请回到网页刷新')
        else:
            logger.exception(f'请求Next Train第三方登录失败: 未返回token: {j_obj}')
            return await message.reply(content='请求登录失败')


async def handle_get_invite_code(message: GroupMessage, **kwargs):
    account = kwargs.get('account')
    timestamp = int(time.time())
    userid = message.author.member_openid
    group_id = account['wechat_id']
    platform = 'wechat'
    data_str: str = f'{userid}@{group_id}@{platform}@{timestamp}'
    client_key = account.get('next_train_client_key')
    sign = hmac.new(client_key.encode('utf-8'), data_str.encode('utf-8'), hashlib.sha256).hexdigest()
    async with httpx.AsyncClient() as client:
        url = f'{urllib.parse.urljoin(os.getenv("REALTIME_API_BASEURL"), "/users/invite-code/get")}'
        resp = await client.post(url, data={
            'group_id': group_id,
            'user_id': userid,
            'platform': platform,
            'sign': sign,
            'timestamp': timestamp,
        })
        resp.raise_for_status()
    j_obj: dict = resp.json()
    if not (failed := j_obj.get('data').get("failed")) and (invite_code := j_obj.get('data')):
        return await message.reply(content=f'我们诚挚欢迎你加入「下一班車」，邀请码为：{invite_code}  5分钟内有效')
    else:
        return await message.reply(content='获取邀请码失败')
