from fastapi import APIRouter

from app.api.v1.endpoints import health, jobs, webhooks, websocket

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(webhooks.router, tags=["webhooks"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(websocket.router, tags=["websocket"])
