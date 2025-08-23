import asyncio

from app.utils.wechat_utils import load_account_info, get_access_token


def test_get_token():
    account = 'zhjl'
    account_info = load_account_info(account)
    print(asyncio.run(get_access_token(account_info)))


if __name__ == '__main__':
    test_get_token()
