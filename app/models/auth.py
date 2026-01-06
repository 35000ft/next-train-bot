from sqlalchemy import Column, String, TIMESTAMP, BigInteger, Boolean, func, Text, ForeignKey, SmallInteger
from sqlalchemy.orm import relationship

from .base import Base

schema = 'next_train_bot'


class UserRole(Base):
    __tablename__ = 'tb_user_role'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_id = Column(BigInteger, ForeignKey(f'{schema}.tb_role.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey(f'{schema}.tb_user.id'), nullable=True)
    is_active = Column(SmallInteger, default=True, nullable=True)
    create_time = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    __table_args__ = {
        'schema': schema
    }
    role = relationship("Role")


class BotUser(Base):
    __tablename__ = 'tb_user'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    openid = Column(String(255), nullable=True)
    password = Column(String(128), nullable=False)
    username = Column(String(150), nullable=False)
    email = Column(String(255), nullable=True)
    is_active = Column(SmallInteger, nullable=False)
    create_time = Column(TIMESTAMP, nullable=True, default=func.current_timestamp())

    roles = relationship("UserRole")

    # permissions
    def __repr__(self):
        return f"<BotUser(id={self.id}, username='{self.username}', email='{self.email}')>"

    __table_args__ = {
        'schema': schema
    }


class UserGroupRel(Base):
    __tablename__ = "tb_user_group_rel"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    user_openid = Column(String(255), nullable=False)
    group_openid = Column(String(255), nullable=False)
    group_user_openid = Column(String(255), nullable=False)

    __table_args__ = {
        'schema': schema
    }

    def __repr__(self):
        return (
            f"<UserGroupRel(id={self.id}, user_id={self.user_id}, "
            f"user_openid='{self.user_openid}', group_openid='{self.group_openid}', "
            f"group_user_openid='{self.group_user_openid}')>"
        )


class Role(Base):
    __tablename__ = 'tb_role'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True, comment='权限组名称')
    unikey = Column(String(255), nullable=True)
    is_active = Column(SmallInteger, nullable=True, default=True)
    create_time = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    update_time = Column(TIMESTAMP, nullable=True)
    __table_args__ = {
        'schema': schema
    }


class Permission(Base):
    __tablename__ = 'tb_permission'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    code = Column(String(255), nullable=False)
    params = Column(Text, nullable=True)
    is_active = Column(SmallInteger, default=True, nullable=True)
    create_time = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    update_time = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    __table_args__ = {
        'schema': schema
    }


class RolePermission(Base):
    __tablename__ = 'tb_role_permission'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_id = Column(BigInteger, ForeignKey(f'{schema}.tb_role.id'), nullable=False)
    permission_id = Column(BigInteger, ForeignKey(f'{schema}.tb_permission.id'), nullable=True)
    is_active = Column(SmallInteger, default=True, nullable=True)
    create_time = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    __table_args__ = {
        'schema': schema
    }
