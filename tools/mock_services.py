"""
Stand-ins for the Sandbox and AI engine services, so you can test the
whole backend pipeline before your teammates' real services exist.
Matches the Stage 2/3 and Stage 4/5 contracts from the schema doc
exactly — swap SANDBOX_BASE_URL / AI_ENGINE_BASE_URL to the real
services later and nothing else changes.

Run:
    python tools/mock_services.py

Serves:
    http://localhost:9000/execute   (fake sandbox — Stage 2 -> Stage 3)
    http://localhost:9100/analyze   (fake AI engine — Stage 4 -> Stage 5)
"""
import asyncio

import uvicorn
from fastapi import FastAPI

sandbox_app = FastAPI(title="mock-sandbox")
ai_app = FastAPI(title="mock-ai-engine")


@sandbox_app.post("/execute")
async def execute(payload: dict):
    """Always 'succeeds' with 2 passing tests, 1 failing — enough to exercise the AI stage."""
    return {
        "job_id": payload["job_id"],
        "status": "test_failures",
        "exit_code": 1,
        "execution_time_ms": 2310,
        "resource_usage": {"cpu_percent": 35, "memory_mb": 180},
        "stdout": "collected 3 items\n...",
        "stderr": "",
        "diff": "diff --git a/src/auth.py b/src/auth.py\n+ query = f\"SELECT * FROM users WHERE id={user_id}\"",
        "files_changed": ["src/auth.py"],
        "test_results": {
            "passed": 2,
            "failed": 1,
            "failures": [{"test_name": "test_login_invalid_token", "message": "AssertionError: expected 401, got 200"}],
        },
    }


@ai_app.post("/analyze")
async def analyze(payload: dict):
    """Always returns one critical security issue, matching the Stage 5 example in the schema doc."""
    return {
        "job_id": payload["job_id"],
        "merge_readiness_score": 62,
        "summary": "1 failing test and one potential SQL injection risk in auth.py",
        "issues": [
            {
                "type": "security",
                "severity": "critical",
                "file": "src/auth.py",
                "line": 47,
                "description": "Raw string interpolation used in SQL query",
                "suggested_fix": "Use parameterized query via cursor.execute(query, params)",
            }
        ],
        "recommendation": "request_changes",
    }


async def main():
    sandbox_server = uvicorn.Server(uvicorn.Config(sandbox_app, host="0.0.0.0", port=9000, log_level="info"))
    ai_server = uvicorn.Server(uvicorn.Config(ai_app, host="0.0.0.0", port=9100, log_level="info"))
    await asyncio.gather(sandbox_server.serve(), ai_server.serve())


if __name__ == "__main__":
    asyncio.run(main())
