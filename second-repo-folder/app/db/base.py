from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. All models in app/models/ inherit from this."""
    pass


# Import models here so Base.metadata sees them (used by create_all in main.py's
# dev-mode startup, and by Alembic's env.py for autogenerate).
from app.models import job, execution_result, ai_review, issue  # noqa: E402,F401
