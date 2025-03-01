from enum import StrEnum, auto

from passlib.context import CryptContext
from sqlalchemy import Column, String, Enum
from sqlalchemy.orm import relationship

from src.dependencies.mysql import Base
from src.models.mysql.mixin import BaseMixin

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

    device_list = relationship(
        "Device",
        back_populates="user",
        # User, Device 모델이 1:N 관계이므로 cascade 옵션을 사용하여 부모 객체(User)가 삭제될 때 자식 객체(Device)도 삭제되도록 설정
        # 하지만 두 모델이 '독립적'으로 동작하기 위해서 의도적으로 cascade 옵션을 주석 처리함
        # cascade="all, delete-orphan"
    )

    def set_password(self, plain_password):
        self.hashed_password = pwd_context.hash(plain_password)

    def verify_password(self, plain_password):
        # 입력된 비밀번호가 저장된 해시와 일치하는지 확인
        return pwd_context.verify(plain_password, self.hashed_password)
