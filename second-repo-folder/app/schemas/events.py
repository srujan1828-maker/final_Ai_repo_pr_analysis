"""
Stage 7: Backend -> Frontend (WebSocket events, real-time).

These are plain dict builders rather than a strict Pydantic response
model, because they're fire-and-forget broadcasts (see
core/websocket_manager.py) — there's no caller waiting on a validated
return type, and keeping them as small functions makes each call site
in review_service.py read as "what happened", not "which schema".
"""
import uuid
from typing import Any


def job_created(job_id: uuid.UUID, timestamp: str) -> dict[str, Any]:
    return {"event": "job_created", "job_id": str(job_id), "timestamp": timestamp}


def sandbox_started(job_id: uuid.UUID) -> dict[str, Any]:
    return {"event": "sandbox_started", "job_id": str(job_id)}


def sandbox_completed(job_id: uuid.UUID, passed: int, failed: int) -> dict[str, Any]:
    return {
        "event": "sandbox_completed",
        "job_id": str(job_id),
        "test_summary": {"passed": passed, "failed": failed},
    }


def ai_review_started(job_id: uuid.UUID) -> dict[str, Any]:
    return {"event": "ai_review_started", "job_id": str(job_id)}


def ai_review_completed(job_id: uuid.UUID, score: int, issue_count: int) -> dict[str, Any]:
    return {
        "event": "ai_review_completed",
        "job_id": str(job_id),
        "score": score,
        "issue_count": issue_count,
    }


def github_posted(job_id: uuid.UUID) -> dict[str, Any]:
    return {"event": "github_posted", "job_id": str(job_id)}


def job_failed(job_id: uuid.UUID, stage: str, reason: str) -> dict[str, Any]:
    return {"event": "job_failed", "job_id": str(job_id), "stage": stage, "reason": reason}
