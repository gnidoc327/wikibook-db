from sqlalchemy import Column, String

from ch05.dependencies.mysql import Base
from ch05.models.mixin import BaseMixin


class Board(Base, BaseMixin):
    __tablename__ = "board"

    title = Column(String(100), nullable=False, comment="게시판 제목")
    description = Column(String(500), nullable=False, comment="게시판 설명")
