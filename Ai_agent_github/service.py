from __future__ import annotations

import logging
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from models import AnalyzeRequest, AnalyzeResponse, safe_default_response
from graph import analyze_code

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Code Review Agent",
    description="Automated code review powered by LLM analysis",
    version="1.0.0",
)


async def _forward_result(payload: dict) -> None:
    """POST the final result to the configured callback URL (fire-and-forget)."""
    callback_url = os.getenv("CALLBACK_URL")
    if not callback_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(callback_url, json=payload)
            logger.info("Forwarded result to %s — status %s", callback_url, resp.status_code)
    except Exception as exc:
        logger.warning("Failed to forward result to %s: %s", callback_url, exc)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> JSONResponse:
    """Analyze a code diff and return review results.

    Never raises, never returns non-JSON.
    """
    try:
        result = await analyze_code(request)
        payload = result.model_dump(mode="json")
    except Exception:
        fallback = safe_default_response(request.job_id)
        payload = fallback.model_dump(mode="json")

    await _forward_result(payload)
    return JSONResponse(content=payload)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/test-llm")
async def test_llm() -> JSONResponse:
    """Quick diagnostic: verify LLM connectivity and configuration."""
    from graph import _build_llm
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("NVIDIA_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )
    if not api_key or api_key.endswith("your_nvidia_api_key_here"):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "LLM_API_KEY in .env is still set to placeholder 'nvapi-your_nvidia_api_key_here'. Please replace it with your actual NVIDIA NIM API key starting with 'nvapi-'.",
            },
        )

    try:
        llm = _build_llm()
        response = await llm.ainvoke("Respond with exactly: {\"status\": \"ok\"}")
        return JSONResponse(content={
            "status": "ok",
            "model": os.getenv("LLM_MODEL"),
            "llm_response": response.content,
        })
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "model_used": os.getenv("LLM_MODEL"),
            },
        )
