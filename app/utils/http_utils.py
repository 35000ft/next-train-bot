import os

import httpx
from botpy import logging

nmtr_headers = {
    'accept': 'application/json,text/plain',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'X-SOURCE': F"NEXT-TRAIN-BOT@{os.getenv('APP_ID')}"
}
logger = logging.get_logger()


async def fetch(_url, method: str = 'get', **kwargs):
    logger.info(f'fetch url:{_url} method:{method}')
    if method == 'get':
        resp = httpx.get(_url, headers=nmtr_headers)
    elif method == 'post':
        _body = kwargs.get('data')
        resp = httpx.post(_url, headers=nmtr_headers, data=_body)
    else:
        raise Exception('Method must be "get" or "post"')
    if resp.status_code == 200 and (j_obj := resp.json()):
        if j_obj['failed']:
            return None
        else:
            return j_obj['data'] if 'data' in j_obj else j_obj
    else:
        logger.warning(
            f'fetch url:{_url} method:{method} failed, status_code:{resp.status_code} text:{resp.text[0:100]}...')
        return None
