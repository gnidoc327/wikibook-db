from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from src.dependencies.mysql import Base
from src.models.mysql.mixin import BaseMixin
from src.models.mysql.user import User


class Notice(Base, BaseMixin):
    __tablename__ = "notice"

    title = Column(String(50), nullable=False, comment="공지사항 제목")
    content = Column(
        LONGTEXT, nullable=False, comment="공지사항 내용. 최대 4GB까지 저장 가능"
    )
    author_id = Column(Integer, nullable=False, comment="글 작성자", index=True)
    view_count = Column(Integer, nullable=False, comment="조회 수", default=0)

    author = relationship(
        User,
        primaryjoin="Article.author_id == User.id",
        foreign_keys="Article.author_id",
    )
    board = relationship(
        "Board",
        primaryjoin="Article.board_id == Board.id",
        foreign_keys="Article.board_id",
    )
