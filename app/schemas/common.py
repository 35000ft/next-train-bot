from pydantic import BaseModel


class BotCommand(BaseModel):
    name: str
    handler: str
    help: str
    example: str
