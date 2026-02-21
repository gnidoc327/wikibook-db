from sqlalchemy import Column, Integer, Text, String

from ch03.dependencies.mysql import Base
from ch03.models.mixin import BaseMixin


class Article(Base, BaseMixin):
    __tablename__ = "article"

    title = Column(String(200), nullable=False, comment="게시글 제목")
    content = Column(Text, nullable=False, comment="게시글 내용")
    author_id = Column(Integer, nullable=True, comment="작성자 ID")
    board_id = Column(Integer, nullable=True, comment="게시판 ID")
