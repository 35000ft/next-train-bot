import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(..., max_length=150)
    password: str = Field(str(uuid.uuid4().hex), min_length=6)
    email: Optional[EmailStr] = None
    openid: str
