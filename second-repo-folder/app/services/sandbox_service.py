"""
Backend -> Sandbox client (Stage 2 request, Stage 3 response).

The real sandbox is a code-runner, not a CI-runner: it takes raw code
via POST /run and returns {stdout, stderr, exit_code, execution_time,
cpu_percent, memory_used, ...}. This module translates that response
into the SandboxExecutionResult schema the rest of the pipeline expects,
so nothing downstream needs to change.
"""
import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.common import SandboxStatus
from app.schemas.review import ResourceUsage, SandboxCodeRequest, SandboxExecutionResult
from app.services.base import ServiceClientError, post_json

logger = get_logger(__name__)
settings = get_settings()


async def run_sandbox(
    job_id: uuid.UUID, code: str, diff: str, files_changed: list[str] | None = None
) -> SandboxExecutionResult:
    """
    Send code to the sandbox's POST /run endpoint and translate the
    response into a SandboxExecutionResult.

    Parameters
    ----------
    job_id : uuid.UUID
        The pipeline job ID — carried through for logging and the result payload.
    code : str
        The raw code / diff content to execute in the sandbox.
    diff : str
        The unified diff text to store on the result (for the AI engine).
    files_changed : list[str] | None
        Optional list of filenames that changed (extracted from the diff).
    """
    request = SandboxCodeRequest(code=code)

    try:
        raw = await post_json(
            f"{settings.sandbox_base_url}/run",
            request.model_dump(),
            timeout=settings.sandbox_timeout_seconds,
        )
        return _translate_response(job_id, raw, diff, files_changed)
    except ServiceClientError as e:
        logger.error(f"Sandbox call failed for job {job_id}: {e.detail}")
        return SandboxExecutionResult(
            job_id=job_id,
            status=SandboxStatus.sandbox_error,
            stderr=f"Could not reach sandbox service: {e.detail}",
        )


def _translate_response(
    job_id: uuid.UUID, raw: dict, diff: str, files_changed: list[str] | None
) -> SandboxExecutionResult:
    """
    Map the sandbox's response shape into our SandboxExecutionResult.

    Sandbox returns:
        {stdout, stderr, exit_code, execution_time, cpu_percent,
         memory_used, memory_total, disk_used, disk_total}

    We map:
        exit_code == 0           -> status = success
        exit_code != 0 / None    -> status = test_failures
        execution_time (seconds) -> execution_time_ms (milliseconds)
        cpu_percent              -> resource_usage.cpu_percent
        memory_used              -> resource_usage.memory_mb
    """
    exit_code = raw.get("exit_code")
    if exit_code is not None and exit_code == 0:
        status = SandboxStatus.success
    else:
        status = SandboxStatus.test_failures

    # execution_time comes as seconds (float), we store milliseconds (int)
    execution_time = raw.get("execution_time")
    execution_time_ms = int(execution_time * 1000) if execution_time is not None else None

    # Resource metrics — sandbox may return null for any of these.
    # memory_used comes back in bytes; we store megabytes.
    cpu_percent = raw.get("cpu_percent")
    memory_used = raw.get("memory_used")
    memory_mb = round(memory_used / (1024 * 1024), 1) if memory_used is not None else None
    resource_usage = None
    if cpu_percent is not None or memory_mb is not None:
        resource_usage = ResourceUsage(cpu_percent=cpu_percent, memory_mb=memory_mb)

    return SandboxExecutionResult(
        job_id=job_id,
        status=status,
        exit_code=exit_code,
        execution_time_ms=execution_time_ms,
        resource_usage=resource_usage,
        stdout=raw.get("stdout"),
        stderr=raw.get("stderr"),
        diff=diff,
        files_changed=files_changed or [],
    )
