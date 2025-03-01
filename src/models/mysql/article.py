from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from src.dependencies.mysql import Base
from src.models.mysql.mixin import BaseMixin
from src.models.mysql.user import User


class Article(Base, BaseMixin):
    __tablename__ = "article"

    title = Column(String(50), nullable=False, comment="글 제목")
    content = Column(
        LONGTEXT, nullable=False, comment="글 내용. 최대 4GB까지 저장 가능"
    )
    author_id = Column(Integer, nullable=False, comment="글 작성자", index=True)
    like_count = Column(Integer, nullable=False, comment="좋아요 수", default=0)
    view_count = Column(Integer, nullable=False, comment="조회 수", default=0)
    board_id = Column(Integer, nullable=False, comment="게시판 ID", index=True)

    is_hot_article = Column(
        Boolean,
        nullable=False,
        comment="인기글 여부(0/false: 일반글, 1/true: 인기글)",
        default=False,
    )

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
