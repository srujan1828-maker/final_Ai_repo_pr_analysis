import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExecutionResult(Base):
    """
    Stage 3 payload, stored as-received. test_results is kept as raw
    JSONB rather than normalized into its own table — per the schema
    doc, that's a deliberate hackathon-scope call, not an oversight.
    """

    __tablename__ = "execution_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.job_id"), nullable=False, unique=True)

    status: Mapped[str] = mapped_column(String, nullable=False)  # success | test_failures | timeout | sandbox_error
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resource_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    files_changed: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    test_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {passed, failed, failures: [...]}

    job: Mapped["Job"] = relationship(back_populates="execution_result")
