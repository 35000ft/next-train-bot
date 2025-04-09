"""
中国国铁插件
"""
import os
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

import httpx
import pytz
import urllib3.util
from botpy import logging
from botpy.message import GroupMessage, C2CMessage
from pydantic import BaseModel

_headers = {
    'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
}

logger = logging.get_logger()


class EmuTrain(BaseModel):
    date: datetime
    emu_no: str
    train_no: str


async def handle_query_emu_no(message: GroupMessage | C2CMessage, train_no: str, **kwargs):
    if train_no[0:1] not in ['D', 'C', 'G', 'S']:
        await message.reply(content=f'不支持的车次:{train_no}')
        return
    now = datetime.now(tz=ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)
    url = f'{os.getenv("RAILRE_BASEURL")}/train/{train_no}'
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=_headers)
            resp.raise_for_status()
            content = resp.json()
            if not content:
                await message.reply(content=f'没有查到车次{train_no}的动车组担当信息')
                return
    except Exception as e:
        logger.exception(e)
        await message.reply(content=f'查询车次动车组担当失败:{train_no}')
        return
    emu_train_list: List[EmuTrain] = [EmuTrain(**x) for x in content]
    if not emu_train_list:
        await message.reply(content=f'没有查到车次{train_no}的动车组担当信息')

    target_date_record = [record for record in emu_train_list if record.date.date() == now.date()]
    if target_date_record:
        await message.reply(
            content=f'车次:{train_no} {now.strftime("%Y-%m-%d")} 担当动车组:{",".join([x.emu_no for x in target_date_record])}\n来源:rail_re')
        return
    else:
        r_content = f'未查询到{train_no}在{now.strftime("%Y-%m-%d")}的担当动车组信息，显示最近三条:\n'
        rows = [f"{x.date.strftime('%Y-%m-%d')}:{x.emu_no}" for x in emu_train_list[0:3]]
        r_content += '\n'.join(rows)
        r_content += '\n'
        r_content += '来源:rail_re'
        await message.reply(content=r_content)
        return
