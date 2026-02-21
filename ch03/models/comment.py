from sqlalchemy import Column, Integer, Text

from ch03.dependencies.mysql import Base
from ch03.models.mixin import BaseMixin


class Comment(Base, BaseMixin):
    __tablename__ = "comment"

    content = Column(Text, nullable=False, comment="댓글 내용")
    author_id = Column(Integer, nullable=True, comment="작성자 ID")
    article_id = Column(Integer, nullable=True, comment="게시글 ID")
