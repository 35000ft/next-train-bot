import botpy

from app.config import Config
from bot.next_train_robot import NextTrainClient

if __name__ == "__main__":
    # 通过kwargs，设置需要监听的事件通道
    intents = botpy.Intents(public_messages=True)
    client = NextTrainClient(intents=intents)
    client.run(appid=Config.APP_ID, secret=Config.SECRET)
