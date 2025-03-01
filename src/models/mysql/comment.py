from sqlalchemy import Column, Integer
from sqlalchemy.dialects.mysql import TINYTEXT
from sqlalchemy.orm import relationship

from src.dependencies.mysql import Base
from src.models.mysql.mixin import BaseMixin
from src.models.mysql.user import User


class Comment(Base, BaseMixin):
    __tablename__ = "comment"

    content = Column(
        TINYTEXT, nullable=False, comment="댓글 내용. 최대 64KB까지 저장 가능"
    )
    author_id = Column(Integer, nullable=False, comment="댓글 작성자", index=True)
    like_count = Column(Integer, nullable=False, comment="좋아요 수", default=0)
    article_id = Column(Integer, nullable=False, comment="글 ID", index=True)

    author = relationship(
        User,
        primaryjoin="Article.author_id == User.id",
        foreign_keys="Article.author_id",
    )
    article = relationship(
        "Article",
        primaryjoin="Comment.article_id == Article.id",
        foreign_keys="Comment.article_id",
    )
