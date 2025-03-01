from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.orm import relationship

from src.dependencies.mysql import Base
from src.models.mysql.mixin import BaseMixin


class Device(Base, BaseMixin):
    __tablename__ = "device"

    name = Column(String(50), nullable=False, comment="기기명")
    type = Column(
        String(50), nullable=False, comment="기기종류(android, ios, chrome...)"
    )
    os_version = Column(String(200), nullable=False, comment="OS 버전(sequoia 15.3.2)")
    token = Column(String(100), nullable=False, comment="푸시 알림 토큰")
    is_active = Column(Boolean, default=True, comment="활성화 여부")

    user_id = Column(Integer, nullable=False, comment="사용자 ID", index=True)

    user = relationship(
        "User",
        primaryjoin="Device.user_id == User.id",
        foreign_keys="Device.user_id",
        back_populates="device_list",
    )
