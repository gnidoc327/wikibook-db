from enum import StrEnum, auto

from passlib.context import CryptContext
from sqlalchemy import Column, String, Enum

from ch03.dependencies.mysql import Base
from ch03.models.mixin import BaseMixin

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRole(StrEnum):
    admin = auto()
    member = auto()
    guest = auto()


class User(Base, BaseMixin):
    __tablename__ = "user"

    name = Column(String(50), nullable=False, comment="이름(ex - 홍길동)")
    email = Column(String(100), index=True, nullable=False, comment="이메일")
    hashed_password = Column(String(100), comment="암호화된 비밀번호")
    role = Column(Enum(UserRole), default=UserRole.guest, comment="권한")

    def set_password(self, plain_password):
        self.hashed_password = pwd_context.hash(plain_password)

    def verify_password(self, plain_password):
        return pwd_context.verify(plain_password, self.hashed_password)
