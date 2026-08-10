"""
Models package. Imports ensure all models are registered with Base.metadata
so that create_all() in app/main.py's lifespan can see and create them.
"""
from app.models.job import Job, JobStatus
from app.models.execution_result import ExecutionResult
from app.models.ai_review import AIReview
from app.models.issue import Issue

__all__ = ["Job", "JobStatus", "ExecutionResult", "AIReview", "Issue"]
