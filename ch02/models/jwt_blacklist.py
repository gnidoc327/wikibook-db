from sqlalchemy import Column, DateTime, String

from ch02.dependencies.mysql import Base
from ch02.models.mixin import BaseMixin


class JwtBlacklist(Base, BaseMixin):
    __tablename__ = "jwt_blacklist"

    token = Column(String(512), nullable=False, unique=True, comment="블랙리스트 토큰")
    expiration_time = Column(DateTime, nullable=False, comment="토큰 만료 시간")
    username = Column(String(50), nullable=False, comment="사용자명")
