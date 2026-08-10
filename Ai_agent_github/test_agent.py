from __future__ import annotations

import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from models import AnalyzeRequest, AnalyzeResponse, Issue, Recommendation, Severity, IssueType
from graph import (
    _parse_diff,
    aggregate_node,
    validate_node,
    analyze_code,
    build_graph,
    GraphState,
    SEVERITY_WEIGHTS,
)
from service import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r") as f:
        return json.load(f)


def validate_response_schema(data: dict) -> AnalyzeResponse:
    """Validate response matches Pydantic schema. Raises on failure."""
    return AnalyzeResponse.model_validate(data)


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------
class TestSchemaValidation:
    @pytest.mark.parametrize(
        "fixture_name",
        ["clean_pr.json", "failing_tests.json", "security_bug.json"],
    )
    def test_request_schema_valid(self, fixture_name: str):
        data = load_fixture(fixture_name)
        request = AnalyzeRequest.model_validate(data)
        assert request.job_id
        assert request.diff

    def test_response_schema_valid(self):
        response = AnalyzeResponse(
            job_id="test-001",
            merge_readiness_score=85,
            summary="All good",
            issues=[],
            recommendation=Recommendation.APPROVE,
        )
        data = response.model_dump(mode="json")
        assert data["merge_readiness_score"] == 85
        assert data["recommendation"] == "approve"

    def test_response_score_clamped(self):
        response = AnalyzeResponse(
            job_id="test",
            merge_readiness_score=150,
            summary="test",
            issues=[],
            recommendation=Recommendation.APPROVE,
        )
        assert response.merge_readiness_score == 100

    def test_issue_schema(self):
        issue = Issue(
            type=IssueType.SECURITY,
            severity=Severity.CRITICAL,
            file="app.py",
            line=10,
            description="SQL injection",
            suggested_fix="Use parameterized queries",
        )
        data = issue.model_dump(mode="json")
        assert data["type"] == "security"
        assert data["severity"] == "critical"


# ---------------------------------------------------------------------------
# Diff parsing tests
# ---------------------------------------------------------------------------
class TestDiffParsing:
    def test_parse_clean_pr(self):
        data = load_fixture("clean_pr.json")
        file_diffs = _parse_diff(data["diff"])
        assert len(file_diffs) >= 1
        filenames = [fd.filename for fd in file_diffs]
        assert any("string_helpers" in f for f in filenames)

    def test_parse_security_bug(self):
        data = load_fixture("security_bug.json")
        file_diffs = _parse_diff(data["diff"])
        assert len(file_diffs) >= 2
        filenames = [fd.filename for fd in file_diffs]
        assert any("search" in f for f in filenames)
        assert any("crypto" in f for f in filenames)

    def test_parse_empty_diff(self):
        file_diffs = _parse_diff("")
        assert file_diffs == []


# ---------------------------------------------------------------------------
# Aggregate node tests
# ---------------------------------------------------------------------------
class TestAggregation:
    def _make_issue(self, severity: str, issue_type: str = "bug") -> Issue:
        return Issue(
            type=IssueType(issue_type),
            severity=Severity(severity),
            file="test.py",
            line=1,
            description="test issue",
            suggested_fix="fix it",
        )

    def test_no_issues_score_100(self):
        state: GraphState = {
            "job_id": "test",
            "diff": "",
            "security_issues": [],
            "bug_issues": [],
            "performance_issues": [],
            "quality_issues": [],
        }
        result = aggregate_node(state)
        assert result["merge_readiness_score"] == 100
        assert result["recommendation"] == "approve"

    def test_critical_caps_at_50(self):
        state: GraphState = {
            "job_id": "test",
            "diff": "",
            "security_issues": [self._make_issue("critical", "security")],
            "bug_issues": [],
            "performance_issues": [],
            "quality_issues": [],
        }
        result = aggregate_node(state)
        assert result["merge_readiness_score"] <= 50

    def test_severity_weight_deduction(self):
        state: GraphState = {
            "job_id": "test",
            "diff": "",
            "security_issues": [],
            "bug_issues": [self._make_issue("high")],
            "performance_issues": [],
            "quality_issues": [self._make_issue("low", "quality")],
        }
        result = aggregate_node(state)
        expected = 100 - SEVERITY_WEIGHTS["high"] - SEVERITY_WEIGHTS["low"]
        assert result["merge_readiness_score"] == expected

    def test_score_clamps_to_zero(self):
        state: GraphState = {
            "job_id": "test",
            "diff": "",
            "security_issues": [
                self._make_issue("critical", "security"),
                self._make_issue("critical", "security"),
                self._make_issue("critical", "security"),
            ],
            "bug_issues": [],
            "performance_issues": [],
            "quality_issues": [],
        }
        result = aggregate_node(state)
        assert result["merge_readiness_score"] == 0

    def test_block_on_low_score(self):
        state: GraphState = {
            "job_id": "test",
            "diff": "",
            "security_issues": [
                self._make_issue("critical", "security"),
                self._make_issue("high", "security"),
            ],
            "bug_issues": [self._make_issue("high")],
            "performance_issues": [],
            "quality_issues": [],
        }
        result = aggregate_node(state)
        assert result["recommendation"] == "block"


# ---------------------------------------------------------------------------
# Validate node tests
# ---------------------------------------------------------------------------
class TestValidation:
    def test_valid_state_produces_result(self):
        state: GraphState = {
            "job_id": "val-001",
            "diff": "",
            "merge_readiness_score": 85,
            "summary": "All good",
            "all_issues": [],
            "recommendation": "approve",
            "retry_count": 0,
        }
        result = validate_node(state)
        assert result["result"] is not None
        assert result["validation_error"] == ""
        validated = AnalyzeResponse.model_validate(result["result"])
        assert validated.job_id == "val-001"

    def test_fallback_on_repeated_failure(self):
        state: GraphState = {
            "job_id": "fail-001",
            "diff": "",
            "merge_readiness_score": -999,  # invalid but will be clamped
            "summary": "test",
            "all_issues": [],
            "recommendation": "invalid_value",
            "retry_count": 1,
        }
        result = validate_node(state)
        assert result["result"] is not None
        validated = AnalyzeResponse.model_validate(result["result"])
        assert validated.merge_readiness_score == 0
        assert validated.recommendation == Recommendation.BLOCK


# ---------------------------------------------------------------------------
# FastAPI endpoint tests
# ---------------------------------------------------------------------------
class TestAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.parametrize(
        "fixture_name",
        ["clean_pr.json", "failing_tests.json", "security_bug.json"],
    )
    def test_analyze_returns_valid_json(self, client, fixture_name):
        """Post fixture to /analyze with mocked graph, verify schema."""
        fixture_data = load_fixture(fixture_name)

        # Mock analyze_code to avoid real LLM calls
        mock_response = AnalyzeResponse(
            job_id=fixture_data["job_id"],
            merge_readiness_score=75,
            summary="Mocked review",
            issues=[],
            recommendation=Recommendation.APPROVE,
        )
        with patch("service.analyze_code", new_callable=AsyncMock, return_value=mock_response):
            response = client.post("/analyze", json=fixture_data)

        assert response.status_code == 200
        data = response.json()
        validated = validate_response_schema(data)
        assert validated.job_id == fixture_data["job_id"]

    def test_analyze_never_raises_on_error(self, client):
        """Even if graph explodes, endpoint returns valid JSON."""
        fixture_data = load_fixture("clean_pr.json")
        with patch("service.analyze_code", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            response = client.post("/analyze", json=fixture_data)

        assert response.status_code == 200
        data = response.json()
        validated = validate_response_schema(data)
        assert validated.merge_readiness_score == 0
        assert validated.recommendation == "block"


# ---------------------------------------------------------------------------
# Integration-style tests (mocked LLM)
# ---------------------------------------------------------------------------
class TestIntegration:
    def _mock_llm_response(self, issues: list[dict]) -> str:
        return json.dumps({"issues": issues})

    @pytest.mark.asyncio
    async def test_clean_pr_no_issues(self):
        """Clean PR fixture should produce high score when LLM finds no issues."""
        fixture_data = load_fixture("clean_pr.json")
        request = AnalyzeRequest.model_validate(fixture_data)

        empty_response = MagicMock()
        empty_response.content = self._mock_llm_response([])

        with patch("graph.ChatOpenAI") as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = AsyncMock(return_value=empty_response)
            result = await analyze_code(request)

        assert isinstance(result, AnalyzeResponse)
        assert result.merge_readiness_score == 100
        assert result.recommendation == Recommendation.APPROVE
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_security_bug_detected(self):
        """Security fixture should detect critical issues when LLM reports them."""
        fixture_data = load_fixture("security_bug.json")
        request = AnalyzeRequest.model_validate(fixture_data)

        security_issues = [
            {
                "severity": "critical",
                "file": "app/routes/search.py",
                "line": 17,
                "description": "SQL injection via f-string interpolation",
                "suggested_fix": "Use parameterized queries",
            },
            {
                "severity": "critical",
                "file": "app/routes/search.py",
                "line": 7,
                "description": "Hardcoded API secret",
                "suggested_fix": "Use environment variables",
            },
        ]
        quality_issues = [
            {
                "severity": "high",
                "file": "app/utils/crypto.py",
                "line": 5,
                "description": "MD5 used for password hashing",
                "suggested_fix": "Use bcrypt or argon2",
            },
        ]

        call_count = 0

        async def mock_ainvoke(prompt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if "security" in prompt.lower():
                resp.content = json.dumps({"issues": security_issues})
            elif "quality" in prompt.lower():
                resp.content = json.dumps({"issues": quality_issues})
            else:
                resp.content = json.dumps({"issues": []})
            return resp

        with patch("graph.ChatOpenAI") as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = mock_ainvoke
            result = await analyze_code(request)

        assert isinstance(result, AnalyzeResponse)
        assert result.merge_readiness_score <= 50  # capped by critical
        assert result.recommendation in (Recommendation.BLOCK, Recommendation.REQUEST_CHANGES)
        assert any(i.type == IssueType.SECURITY for i in result.issues)

    @pytest.mark.asyncio
    async def test_failing_tests_detection(self):
        """Failing tests fixture should detect bug issues."""
        fixture_data = load_fixture("failing_tests.json")
        request = AnalyzeRequest.model_validate(fixture_data)

        bug_issues = [
            {
                "severity": "high",
                "file": "users/models.py",
                "line": 18,
                "description": "Non-nullable field without default breaks existing tests",
                "suggested_fix": "Add blank=True, null=True or provide a default value",
            },
        ]

        async def mock_ainvoke(prompt, *args, **kwargs):
            resp = MagicMock()
            if "bug" in prompt.lower():
                resp.content = json.dumps({"issues": bug_issues})
            else:
                resp.content = json.dumps({"issues": []})
            return resp

        with patch("graph.ChatOpenAI") as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = mock_ainvoke
            result = await analyze_code(request)

        assert isinstance(result, AnalyzeResponse)
        assert result.merge_readiness_score < 100
        assert any(i.type == IssueType.BUG for i in result.issues)

    @pytest.mark.asyncio
    async def test_llm_timeout_returns_fallback(self):
        """If all LLM calls time out, should return safe default."""
        fixture_data = load_fixture("clean_pr.json")
        request = AnalyzeRequest.model_validate(fixture_data)

        async def mock_ainvoke(prompt, *args, **kwargs):
            raise asyncio.TimeoutError()

        with patch("graph.ChatOpenAI") as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = mock_ainvoke
            result = await analyze_code(request)

        # Even on total LLM failure, we get a valid response
        assert isinstance(result, AnalyzeResponse)
        # With no issues detected (timeout = empty), should still be valid
        validate_response_schema(result.model_dump(mode="json"))
