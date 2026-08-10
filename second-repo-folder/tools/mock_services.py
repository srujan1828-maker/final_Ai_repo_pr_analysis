"""
Stand-ins for the Sandbox and AI engine services, so you can test the
whole backend pipeline before your teammates' real services exist.

The mock sandbox mirrors the real code-runner API (POST /run) and returns
the same response shape the live service uses. Swap SANDBOX_BASE_URL /
AI_ENGINE_BASE_URL to the real services later and nothing else changes.

Run:
    python tools/mock_services.py

Serves:
    http://localhost:9000/run      (fake sandbox — Stage 2 -> Stage 3)
    http://localhost:9100/analyze (fake AI engine — Stage 4 -> Stage 5)
"""
import asyncio
import contextlib
import io
import time

import uvicorn
from fastapi import FastAPI

sandbox_app = FastAPI(title="mock-sandbox")
ai_app = FastAPI(title="mock-ai-engine")


@sandbox_app.post("/run")
async def run_code(payload: dict):
    """
    Mimics the real sandbox's POST /run: executes code and returns
    stdout/stderr/exit_code plus resource metrics.
    """
    code = payload.get("code", "")
    stdout = ""
    stderr = ""
    exit_code = 0

    start = time.perf_counter()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            exec(compile(code, "<sandbox>", "exec"), {})
        except Exception as e:
            exit_code = 1
            stderr = f"{type(e).__name__}: {e}"
    stdout = buf.getvalue()
    execution_time = round(time.perf_counter() - start, 4)

    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "execution_time": execution_time,
        "cpu_percent": 12.5,
        "memory_used": 55 * 1024 * 1024,
        "memory_total": 512 * 1024 * 1024,
        "disk_used": 1024 * 1024 * 1024,
        "disk_total": 20 * 1024 * 1024 * 1024,
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
