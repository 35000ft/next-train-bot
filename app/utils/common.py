import time

from botpy.message import GroupMessage

from app.schemas.weixin import ResponseMsgBody, WechatMedia


class WechatMessage(GroupMessage):
    def __init__(self, user_id: str, data: dict, ):
        super().__init__(None, int(time.time()), data)
        user_dict = {
            'member_openid': user_id,
        }
        self.author = self._User(user_dict)
        self.group_openid = data.get("group_openid", None)
        self.to_username = data.get("to_username", None)
        self.content = data.get("content", None)

    async def reply(self, **kwargs) -> ResponseMsgBody:
        resp = ResponseMsgBody(
            ToUserName=self.author.member_openid,
            FromUserName=self.to_username,
            CreateTime=int(time.time()),
            MsgType="text",
            Content=kwargs.get("content", None))
        if media_info := kwargs.get("media"):
            if isinstance(media_info, WechatMedia):
                return resp.set_media(media_info)
        return resp
