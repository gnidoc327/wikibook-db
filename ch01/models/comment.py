from sqlalchemy import Column, Integer, Text

from ch01.dependencies.mysql import Base
from ch01.models.mixin import BaseMixin


class Comment(Base, BaseMixin):
    __tablename__ = "comment"

    content = Column(Text, nullable=False, comment="댓글 내용")
    author_id = Column(Integer, nullable=True, comment="작성자 user.id")
    article_id = Column(Integer, nullable=True, comment="게시글 article.id")
