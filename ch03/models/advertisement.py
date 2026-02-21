from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from ch03.dependencies.mysql import Base
from ch03.models.mixin import BaseMixin


class Advertisement(Base, BaseMixin):
    __tablename__ = "advertisement"

    title = Column(String(200), nullable=False, comment="광고 제목")
    content = Column(Text, nullable=False, default="", comment="광고 내용")
    is_visible = Column(Boolean, nullable=False, default=True, comment="노출 여부")
    start_date = Column(DateTime, nullable=True, comment="광고 시작일")
    end_date = Column(DateTime, nullable=True, comment="광고 종료일")
    view_count = Column(Integer, nullable=False, default=0, comment="조회수")
    click_count = Column(Integer, nullable=False, default=0, comment="클릭수")
