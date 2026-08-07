import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIReview(Base):
    """Stage 5 payload (minus `issues`, which is its own table)."""

    __tablename__ = "ai_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=False, unique=True)

    merge_readiness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(String, nullable=False)  # approve | request_changes | block

    job: Mapped["Job"] = relationship(back_populates="ai_review")
    issues: Mapped[list["Issue"]] = relationship(back_populates="ai_review", cascade="all, delete-orphan")
