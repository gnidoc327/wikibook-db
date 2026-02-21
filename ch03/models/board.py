from sqlalchemy import Column, String

from ch03.dependencies.mysql import Base
from ch03.models.mixin import BaseMixin


class Board(Base, BaseMixin):
    __tablename__ = "board"

    title = Column(String(100), nullable=False, comment="게시판 제목")
    description = Column(String(500), nullable=False, comment="게시판 설명")
