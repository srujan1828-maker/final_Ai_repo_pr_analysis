from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_db_session

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness — is the process up. Use this for uptime pings / demo-day sanity checks."""
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db_session)):
    """Readiness — is Postgres actually reachable, not just the API process."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "unreachable", "detail": str(e)}
