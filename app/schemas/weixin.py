from typing import Optional, Self, List

import xmltodict
from dicttoxml import dicttoxml
from pydantic import BaseModel, Field


class ReceiveMsgBody(BaseModel):
    ToUserName: Optional[str] = Field(None, description="开发者微信号")
    FromUserName: Optional[str] = Field(None, description="发送消息用户的openId")
    CreateTime: Optional[int] = Field(None, description="消息创建时间")
    MsgType: Optional[str] = Field(None, description="消息类型")
    MsgId: Optional[int] = Field(None, description="消息ID，根据该字段来判重处理")
    Content: Optional[str] = Field(None, description="文本消息的消息体")

    @classmethod
    def from_xml(cls, xml: str) -> Self:
        parsed_dict = xmltodict.parse(xml)
        msg_dict = parsed_dict.get("xml", {})
        return cls(**msg_dict)


class Article(BaseModel):
    Title: str
    Description: Optional[str] = ''
    PicUrl: Optional[str] = None
    Url: str = None


class WechatMedia(BaseModel):
    type: str
    media_id: Optional[str] = None
    created_at: int
    articles: Optional[List[Article]] = []  # 默认为空列表，可以根据需要调整类型

    def __setattr__(self, name, value):
        if name in self.__dict__:
            super().__setattr__(name, value)
        else:
            self.__dict__[name] = value

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    class Config:
        extra = 'allow'


class ResponseMsgBody(BaseModel):
    ToUserName: Optional[str] = Field(None, description="接收方帐号（收到的OpenID）")
    FromUserName: Optional[str] = Field(None, description="开发者微信号")
    CreateTime: Optional[int] = Field(None, description="消息创建时间")
    MsgType: Optional[str] = Field(None, description="消息类型")
    Content: Optional[str] = Field(None, description="文本消息的消息体")
    Image: Optional[dict] = None
    Voice: Optional[dict] = None
    Video: Optional[dict] = None
    Articles: Optional[dict] = None
    ArticleCount: Optional[int] = None

    def __setattr__(self, name, value):
        if name in self.__dict__:
            super().__setattr__(name, value)
        else:
            self.__dict__[name] = value

    def to_xml(self):
        xml_bytes = dicttoxml(self.model_dump(), custom_root='xml', attr_type=False)
        return xml_bytes

    class Config:
        extra = 'allow'

    def set_media(self, media_info: WechatMedia) -> Self:
        media_type: str = media_info.type
        media_type = media_type[0].upper() + media_type[1:]
        self.MsgType = media_type
        if media_info.media_id:
            setattr(self, media_type, {
                'MediaId': media_info.media_id,
            })
        if media_info.articles:
            articles_items = [{'item': x.model_dump()} for x in media_info.articles]
            if articles_items:
                setattr(self, media_type, {
                    'Articles': articles_items,
                })
                setattr(self, media_type, {
                    'ArticleCount': len(articles_items),
                })
        return self
