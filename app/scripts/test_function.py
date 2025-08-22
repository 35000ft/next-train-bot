import asyncio

from botpy.message import GroupMessage

from app.events.auth.login_events import handle_signup_login
from app.utils.wechat_utils import load_account_info


async def main():
    account_info: dict = load_account_info('zhjl')
    payload = {
        'author': {
            'member_openid': "232sr2"
        },
        'group_openid': account_info['wechat_id']
    }
    m = GroupMessage(api=None, event_id='23', data=payload)
    await handle_signup_login(m, None, account=account_info)


asyncio.run(main())
