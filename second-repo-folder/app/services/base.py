"""
Thin wrapper around httpx.AsyncClient shared by the sandbox and AI
service clients, so both get the same timeout/retry/logging behavior
instead of duplicating it.
"""
import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class ServiceClientError(Exception):
    """Raised when an outbound call to sandbox/AI engine fails outright
    (connection error, non-2xx, timeout) after any retries are exhausted."""

    def __init__(self, service: str, detail: str):
        self.service = service
        self.detail = detail
        super().__init__(f"{service} call failed: {detail}")


async def post_json(url: str, payload: dict, timeout: float) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise ServiceClientError(url, f"timed out after {timeout}s") from e
        except httpx.HTTPStatusError as e:
            raise ServiceClientError(url, f"HTTP {e.response.status_code}: {e.response.text[:300]}") from e
        except httpx.RequestError as e:
            raise ServiceClientError(url, str(e)) from e
