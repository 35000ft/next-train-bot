import xmltodict
from pydantic import BaseModel, Field
from typing import Optional, Self
from dicttoxml import dicttoxml


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


class ResponseMsgBody(BaseModel):
    ToUserName: Optional[str] = Field(None, description="接收方帐号（收到的OpenID）")
    FromUserName: Optional[str] = Field(None, description="开发者微信号")
    CreateTime: Optional[int] = Field(None, description="消息创建时间")
    MsgType: Optional[str] = Field(None, description="消息类型")
    Content: Optional[str] = Field(None, description="文本消息的消息体")

    def to_xml(self):
        xml_bytes = dicttoxml(self.model_dump(), custom_root='xml', attr_type=False)
        return xml_bytes
