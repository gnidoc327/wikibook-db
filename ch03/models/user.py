from enum import StrEnum, auto

from passlib.context import CryptContext
from sqlalchemy import Column, DateTime, Enum, String

from ch03.dependencies.mysql import Base
from ch03.models.mixin import BaseMixin

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRole(StrEnum):
    admin = auto()
    member = auto()
    guest = auto()


class User(Base, BaseMixin):
    __tablename__ = "user"

    username = Column(String(50), unique=True, nullable=False, comment="사용자명")
    email = Column(String(100), unique=True, nullable=False, comment="이메일")
    hashed_password = Column(String(100), comment="암호화된 비밀번호")
    role = Column(Enum(UserRole), default=UserRole.member, comment="권한")
    last_login = Column(DateTime, nullable=True, comment="마지막 로그인 시각")

    def set_password(self, plain_password):
        self.hashed_password = pwd_context.hash(plain_password)

    def verify_password(self, plain_password):
        return pwd_context.verify(plain_password, self.hashed_password)
