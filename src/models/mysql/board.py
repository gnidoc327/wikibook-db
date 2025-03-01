from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.orm import relationship

from src.dependencies.mysql import Base
from src.models.mysql.mixin import BaseMixin
from src.models.mysql.user import User


class Board(Base, BaseMixin):
    __tablename__ = "board"

    title = Column(String(50), nullable=False, comment="게시판 제목")
    description = Column(
        Text, nullable=False, comment="게시판 설명. 최대 64KB까지 저장 가능"
    )
    creator_id = Column(Integer, nullable=False, comment="게시판 생성자", index=True)

    creator = relationship(
        User, primaryjoin="Board.creator_id == User.id", foreign_keys="Board.creator_id"
    )
