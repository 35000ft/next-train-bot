import asyncio
import os

import botpy

from app.config import Config
from app.bot.next_train_robot import NextTrainClient
from app.utils.log_utils import setup_logging


async def main():
    intents = botpy.Intents(public_messages=True)
    client = NextTrainClient(intents=intents, is_sandbox=os.getenv('ENV') != 'prod')
    # client = NextTrainClient(intents=intents)
    await client.start(appid=Config.APP_ID, secret=Config.SECRET)


if __name__ == "__main__":
    # 通过kwargs，设置需要监听的事件通道
    setup_logging()
    asyncio.run(main())
