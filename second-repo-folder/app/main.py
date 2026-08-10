from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.base import Base
from app.db.session import engine

settings = get_settings()
setup_logging(debug=settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience only — creates tables from the SQLAlchemy models if
    # they don't exist yet. For anything beyond local dev, use Alembic
    # migrations instead (see alembic/ and the README) so schema changes
    # are tracked, not implicit.
    if settings.should_create_db_tables:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Ensured database tables exist via create_all")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    logger.info(f"{settings.app_name} starting up ({settings.environment})")
    yield
    logger.info(f"{settings.app_name} shutting down")
    await engine.dispose()


app = FastAPI(title="AI Code Review — Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"service": settings.app_name, "status": "running"}
