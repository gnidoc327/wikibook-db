import re

from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import validates

from src.dependencies.mysql import Base
from src.models.mysql.mixin import BaseMixin


HEX_COLOR_PATTERN = re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{8})$")


class Advertisement(Base, BaseMixin):
    """
    배너광고
    """

    __tablename__ = "advertisement"

    title = Column(String(50), nullable=False, comment="광고 제목")
    content = Column(
        MEDIUMTEXT, nullable=False, comment="광고 내용. 최대 16MB까지 저장 가능"
    )
    banner_color = Column(
        String(20),
        nullable=False,
        comment="배너 배경 색상. 16진수 색상 코드로 저장(예: #FFFFFF)",
    )
    is_visible = Column(
        Boolean,
        nullable=False,
        comment="광고 노출 여부(0/false: 미노출, 1/true: 노출)",
        default=False,
    )
    start_date = Column(DateTime, nullable=False, comment="광고 시작일")
    end_date = Column(DateTime, nullable=False, comment="광고 종료일")

    click_count = Column(
        Integer, nullable=False, comment="광고 클릭 수(CPM)", default=0
    )
    view_count = Column(Integer, nullable=False, comment="광고 조회 수(CPC)", default=0)

    @validates("banner_color")
    def validate_banner_color(self, color):
        if not HEX_COLOR_PATTERN.match(color):
            raise ValueError(
                f"Invalid banner_color format: {color}. Expected format: #RRGGBB or #RRGGBBAA"
            )
        return color
