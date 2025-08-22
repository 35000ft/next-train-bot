import hashlib
import hmac
import os
import time
import urllib.parse
import uuid

import httpx
from botpy.message import GroupMessage


async def handle_signup_login(message: GroupMessage, username: str = None, email: str = None, phone: str = None,
                              **kwargs):
    account = kwargs.get('account')
    if not username:
        username = f'botu_{uuid.uuid4()}'
    userid = message.author.member_openid
    group_id = account['wechat_id']
    platform = 'wechat'
    async with httpx.AsyncClient() as client:
        url = f'{urllib.parse.urljoin(os.getenv("REALTIME_API_BASEURL"), "/users/bot-login")}'
        timestamp = int(time.time())
        data_str: str = f'{userid}@{group_id}@{platform}@{timestamp}'
        client_key = account.get('next_train_client_key')
        sign = hmac.new(client_key.encode('utf-8'), data_str.encode('utf-8'), hashlib.sha256).hexdigest()
        resp = await client.post(url, data={
            'username': username,
            'group_id': group_id,
            'user_id': userid,
            'platform': platform,
            'email': email,
            'phone': phone,
            'sign': sign,
            'timestamp': timestamp,
        })
        resp.raise_for_status()
        j_obj: dict = resp.json()
        if token := j_obj.get('data').get("token"):
            login_url = f'{os.getenv("NEXT_TRAIN_PAGE_BASEURL")}/oauth?token={token}&t={timestamp}'
            return await message.reply(content=f'请按此登录:{login_url}')
