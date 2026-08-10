import asyncio
import json
import logging
import os
import re
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    FileDiff,
    Issue,
    IssueType,
    LLMAnalysisResult,
    Recommendation,
    Severity,
    safe_default_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity weights
# ---------------------------------------------------------------------------
SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 40,
    "high": 20,
    "medium": 10,
    "low": 5,
}

LLM_TIMEOUT = 60  # seconds per call

# Check API key at import time
_api_key = os.getenv("LLM_API_KEY", "") or os.getenv("NVIDIA_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
if not _api_key or _api_key.endswith("your_nvidia_api_key_here"):
    logger.warning(
        "⚠️  LLM_API_KEY is not set or using placeholder in .env! "
        "Real LLM calls will fail until a valid key is provided."
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def _merge_issues(left: list[Issue], right: list[Issue]) -> list[Issue]:
    return left + right


class GraphState(TypedDict, total=False):
    job_id: str
    diff: str
    execution_result: dict
    repo_context: dict
    file_diffs: list[FileDiff]
    security_issues: Annotated[list[Issue], _merge_issues]
    bug_issues: Annotated[list[Issue], _merge_issues]
    performance_issues: Annotated[list[Issue], _merge_issues]
    quality_issues: Annotated[list[Issue], _merge_issues]
    all_issues: list[Issue]
    merge_readiness_score: int
    summary: str
    recommendation: str
    validation_error: str
    retry_count: int
    result: dict


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------
def _build_llm() -> ChatOpenAI:
    base_url = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("NVIDIA_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or "dummy-key"
    )
    model_name = os.getenv("LLM_MODEL", "meta/llama-3.1-8b-instruct")

    kwargs = {
        "model": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": 0,
        "request_timeout": LLM_TIMEOUT,
    }

    # Optional response_format if provider supports JSON mode
    if os.getenv("LLM_JSON_MODE", "true").lower() == "true":
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

    return ChatOpenAI(**kwargs)


def _clean_json_str(content: Any) -> dict:
    """Clean markdown fences if present and parse JSON."""
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        content = str(content)
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


async def _call_llm(prompt: str, retry_context: str = "") -> dict:
    """Call LLM with timeout. Returns parsed JSON dict or raises."""
    llm = _build_llm()
    full_prompt = prompt
    if retry_context:
        full_prompt += (
            f"\n\nPrevious attempt failed with error: {retry_context}\n"
            "Please fix the JSON output."
        )
    response = await asyncio.wait_for(
        llm.ainvoke(full_prompt),
        timeout=LLM_TIMEOUT,
    )
    return _clean_json_str(response.content)


# ---------------------------------------------------------------------------
# Parse node
# ---------------------------------------------------------------------------
def _parse_diff(diff: str) -> list[FileDiff]:
    """Split a unified diff into per-file chunks."""
    file_diffs: list[FileDiff] = []
    parts = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.search(r"^\+\+\+ b/(.+)$", part, re.MULTILINE)
        if not m:
            m = re.search(r"^diff --git a/.+ b/(.+)$", part, re.MULTILINE)
        filename = m.group(1) if m else "unknown"
        file_diffs.append(FileDiff(filename=filename, content=part))
    return file_diffs


def parse_node(state: GraphState) -> dict:
    file_diffs = _parse_diff(state["diff"])
    return {
        "file_diffs": file_diffs,
        "security_issues": [],
        "bug_issues": [],
        "performance_issues": [],
        "quality_issues": [],
        "retry_count": 0,
        "validation_error": "",
    }


# ---------------------------------------------------------------------------
# Analysis prompts
# ---------------------------------------------------------------------------
def _build_analysis_prompt(
    analysis_type: str,
    file_diffs: list[FileDiff],
    execution_result: dict,
    repo_context: dict,
) -> str:
    diffs_text = "\n\n".join(
        f"### {fd.filename}\n```\n{fd.content}\n```" for fd in file_diffs
    )
    return f"""You are a senior code reviewer performing a {analysis_type} analysis.

Analyze the following code diff for {analysis_type} issues.

Repository context:
- Language: {repo_context.get('language', 'unknown')}
- Framework: {repo_context.get('framework', 'unknown')}

Execution result:
- Status: {execution_result.get('status', 'unknown')}
- Exit code: {execution_result.get('exit_code', 'N/A')}
- Test results: {json.dumps(execution_result.get('test_results', {}))}
- Stderr: {execution_result.get('stderr', '')[:500]}

Diffs:
{diffs_text}

Respond with a JSON object containing an "issues" array. Each issue must have:
- "severity": one of "critical", "high", "medium", "low"
- "file": the filename where the issue is found
- "line": approximate line number in the new file
- "description": clear description of the {analysis_type} issue
- "suggested_fix": actionable fix suggestion

If no {analysis_type} issues are found, return {{"issues": []}}.
Only report genuine {analysis_type} issues. Do not fabricate issues.
Respond ONLY with valid JSON."""


# ---------------------------------------------------------------------------
# Analysis branch nodes
# ---------------------------------------------------------------------------
async def _run_analysis(
    state: GraphState, analysis_type: str, issue_type: IssueType, state_key: str
) -> dict:
    prompt = _build_analysis_prompt(
        analysis_type,
        state.get("file_diffs", []),
        state.get("execution_result", {}),
        state.get("repo_context", {}),
    )
    try:
        data = await _call_llm(prompt)
        result = LLMAnalysisResult.model_validate(data)
        issues = [
            Issue(
                type=issue_type,
                severity=Severity(i.severity.lower()),
                file=i.file,
                line=i.line,
                description=i.description,
                suggested_fix=i.suggested_fix,
            )
            for i in result.issues
            if i.severity.lower() in [s.value for s in Severity]
        ]
        logger.info("Analysis '%s' found %d issue(s)", analysis_type, len(issues))
        return {state_key: issues}
    except Exception as exc:
        logger.error("Analysis node '%s' failed: %s", analysis_type, exc, exc_info=True)
        return {state_key: []}


async def security_node(state: GraphState) -> dict:
    return await _run_analysis(state, "security", IssueType.SECURITY, "security_issues")


async def bug_node(state: GraphState) -> dict:
    return await _run_analysis(state, "bug", IssueType.BUG, "bug_issues")


async def performance_node(state: GraphState) -> dict:
    return await _run_analysis(
        state, "performance", IssueType.PERFORMANCE, "performance_issues"
    )


async def quality_node(state: GraphState) -> dict:
    return await _run_analysis(state, "quality", IssueType.QUALITY, "quality_issues")


# ---------------------------------------------------------------------------
# Aggregate node
# ---------------------------------------------------------------------------
def aggregate_node(state: GraphState) -> dict:
    all_issues: list[Issue] = (
        state.get("security_issues", [])
        + state.get("bug_issues", [])
        + state.get("performance_issues", [])
        + state.get("quality_issues", [])
    )

    penalty = sum(SEVERITY_WEIGHTS.get(i.severity.value, 0) for i in all_issues)
    score = max(0, min(100, 100 - penalty))

    has_critical = any(i.severity == Severity.CRITICAL for i in all_issues)
    if has_critical and score > 50:
        score = 50

    if has_critical or score < 30:
        recommendation = Recommendation.BLOCK.value
    elif score < 70:
        recommendation = Recommendation.REQUEST_CHANGES.value
    else:
        recommendation = Recommendation.APPROVE.value

    if not all_issues:
        summary = "Code review passed. No significant issues detected."
    else:
        counts: dict[str, int] = {}
        for i in all_issues:
            counts[i.type.value] = counts.get(i.type.value, 0) + 1
        parts = [f"{v} {k}" for k, v in counts.items()]
        summary = (
            f"Found {len(all_issues)} issue(s): {', '.join(parts)}. "
            f"Merge readiness score: {score}/100."
        )

    return {
        "all_issues": all_issues,
        "merge_readiness_score": score,
        "summary": summary,
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# Validate node
# ---------------------------------------------------------------------------
def validate_node(state: GraphState) -> dict:
    job_id = state["job_id"]
    retry_count = state.get("retry_count", 0)

    try:
        response = AnalyzeResponse(
            job_id=job_id,
            merge_readiness_score=state.get("merge_readiness_score", 0),
            summary=state.get("summary", ""),
            issues=state.get("all_issues", []),
            recommendation=Recommendation(state.get("recommendation", "block")),
        )
        return {
            "result": response.model_dump(mode="json"),
            "validation_error": "",
        }
    except Exception as e:
        if retry_count < 1:
            return {
                "validation_error": str(e),
                "retry_count": retry_count + 1,
            }
        fallback = safe_default_response(job_id)
        return {
            "result": fallback.model_dump(mode="json"),
            "validation_error": "",
        }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def should_retry(state: GraphState) -> str:
    if state.get("validation_error"):
        return "aggregate"
    return END


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------
def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("parse", parse_node)
    graph.add_node("security", security_node)
    graph.add_node("bug", bug_node)
    graph.add_node("performance", performance_node)
    graph.add_node("quality", quality_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("validate", validate_node)

    graph.set_entry_point("parse")

    graph.add_edge("parse", "security")
    graph.add_edge("parse", "bug")
    graph.add_edge("parse", "performance")
    graph.add_edge("parse", "quality")

    graph.add_edge("security", "aggregate")
    graph.add_edge("bug", "aggregate")
    graph.add_edge("performance", "aggregate")
    graph.add_edge("quality", "aggregate")

    graph.add_edge("aggregate", "validate")

    graph.add_conditional_edges("validate", should_retry)

    return graph.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def analyze_code(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run the full analysis graph and return validated response."""
    graph = build_graph()

    initial_state: GraphState = {
        "job_id": request.job_id,
        "diff": request.diff,
        "execution_result": request.execution_result.model_dump(),
        "repo_context": request.repo_context.model_dump(),
    }

    try:
        final_state = await asyncio.wait_for(
            graph.ainvoke(initial_state),
            timeout=180,
        )
    except Exception as exc:
        logger.error("Graph execution failed: %s", exc, exc_info=True)
        return safe_default_response(request.job_id)

    if "result" in final_state and final_state["result"]:
        return AnalyzeResponse.model_validate(final_state["result"])

    return safe_default_response(request.job_id)
