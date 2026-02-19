from sqlalchemy import Column, Integer, Boolean, DateTime, func


class BaseMixin:
    """
    모든 모델(테이블)의 공통 컬럼을 정의
    """

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="삭제 여부(0/false: 미삭제, 1/true: 삭제)",
    )
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )
    deleted_at = Column(DateTime, nullable=True)

    def soft_delete(self):
        """
        hard delete 대신 soft delete를 수행. session.commit()까지 호출이 필요함
        """
        self.is_deleted = True
        self.deleted_at = func.now()
