"""Golden-path eval: agent reaches a final answer with expected tool usage."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent import OpsAgent  # noqa: E402
from tools import HANDLERS  # noqa: E402

ALLOWED_TOOLS = set(HANDLERS)
MAX_SAME_TOOL_CALLS = 3
EVIDENCE_MIN_MATCHES = 2

_STOPWORDS = frozenset(
    {
        "service",
        "minutes",
        "hours",
        "level",
        "query",
        "entries",
        "results",
        "deployments",
        "data",
        "true",
        "false",
        "title",
        "steps",
        "author",
    }
)


def _tools_used(state) -> list[str]:
    return [s["tool"] for s in state.steps if s.get("kind") == "action" and s.get("tool")]


def _final_answer(state) -> str:
    answers = [s["content"] for s in state.steps if s.get("kind") == "answer"]
    assert answers, "Agent did not produce a final answer"
    return answers[-1]


def _normalize(text: str) -> str:
    return re.sub(r"[_\s-]+", " ", text.lower())


def _collect_strings(obj, out: list[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_strings(value, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_strings(item, out)


def _evidence_keywords(state) -> list[str]:
    """Distinct terms/phrases from tool observation payloads."""
    seen: set[str] = set()
    keywords: list[str] = []

    for step in state.steps:
        if step.get("kind") != "observation":
            continue
        try:
            payload = json.loads(step["content"])
        except json.JSONDecodeError:
            continue

        strings: list[str] = []
        _collect_strings(payload.get("data", payload), strings)

        for raw in strings:
            text = raw.strip()
            if len(text) < 4:
                continue
            candidates = [text]
            candidates.extend(re.findall(r"[a-zA-Z][a-zA-Z0-9._-]{2,}", text))
            candidates.extend(re.findall(r"v\d+\.\d+\.\d+", text, flags=re.IGNORECASE))

            for candidate in candidates:
                key = candidate.lower()
                if key in _STOPWORDS or key in seen:
                    continue
                seen.add(key)
                keywords.append(candidate)

    return keywords


def assert_only_allowed_tools(tools_used: list[str]) -> None:
    disallowed = sorted(set(tools_used) - ALLOWED_TOOLS)
    assert not disallowed, f"Used disallowed tools: {disallowed}; allowed: {sorted(ALLOWED_TOOLS)}"


def assert_no_excessive_tool_reuse(tools_used: list[str], *, limit: int = MAX_SAME_TOOL_CALLS) -> None:
    overused = {name: count for name, count in Counter(tools_used).items() if count >= limit}
    assert not overused, f"Same tool used >={limit} times: {overused}"


def assert_answer_uses_tool_evidence(state, *, min_matches: int = EVIDENCE_MIN_MATCHES) -> None:
    answer = _final_answer(state)
    keywords = _evidence_keywords(state)
    assert keywords, "No evidence keywords extracted from tool observations"

    matched = [kw for kw in keywords if _normalize(kw) in _normalize(answer)]
    assert len(matched) >= min_matches, (
        f"Final answer matched {len(matched)}/{min_matches} required evidence terms. "
        f"Matched: {matched[:8]}. Sample evidence: {keywords[:12]}. "
        f"Answer preview: {answer[:400]}..."
    )


def _assert_golden_eval(state) -> None:
    tools_used = _tools_used(state)
    assert_only_allowed_tools(tools_used)
    assert_no_excessive_tool_reuse(tools_used)
    assert_answer_uses_tool_evidence(state)


def test_offline_checkout_investigation():
    agent = OpsAgent(offline=True)
    state = agent.run("checkout failures after deploy")

    tools_used = _tools_used(state)
    assert "search_runbook" in tools_used
    assert "check_service_health" in tools_used
    assert state.tool_calls >= 3
    _assert_golden_eval(state)


def test_retry_on_injected_failure():
    agent = OpsAgent(offline=True, inject_failure=True)
    state = agent.run("checkout failures")

    assert state.retries >= 1
    _assert_golden_eval(state)


@pytest.mark.live
def test_live_checkout_investigation():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set — skip live LLM eval")

    agent = OpsAgent(offline=False)
    state = agent.run(
        "Since ~2pm ET, ~18% of checkout attempts fail with 'payment processing unavailable'. "
        "api-gateway shows elevated latency. Recent deploy to checkout-api."
    )

    tools_used = _tools_used(state)
    assert len(tools_used) >= 2, f"Expected multiple tool calls, got: {tools_used}"
    _assert_golden_eval(state)
