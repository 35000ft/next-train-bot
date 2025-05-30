from sqlalchemy import Column, String, TIMESTAMP, BigInteger, Boolean, func
from sqlalchemy.orm import declarative_base


class BotUser(declarative_base()):
    __tablename__ = 'tb_user'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    openid = Column(String(255), nullable=True)
    password = Column(String(128), nullable=False)
    username = Column(String(150), nullable=False)
    email = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False)
    create_time = Column(TIMESTAMP, nullable=True, default=func.current_timestamp())

    def __repr__(self):
        return f"<BotUser(id={self.id}, username='{self.username}', email='{self.email}')>"

    __table_args__ = {
        'schema': 'next_train_bot'
    }


class UserGroupRel(declarative_base()):
    __tablename__ = "tb_user_group_rel"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    user_openid = Column(String(255), nullable=False)
    group_openid = Column(String(255), nullable=False)
    group_user_openid = Column(String(255), nullable=False)

    __table_args__ = {
        'schema': 'next_train_bot'
    }

    def __repr__(self):
        return (
            f"<UserGroupRel(id={self.id}, user_id={self.user_id}, "
            f"user_openid='{self.user_openid}', group_openid='{self.group_openid}', "
            f"group_user_openid='{self.group_user_openid}')>"
        )
