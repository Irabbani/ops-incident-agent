"""Deterministic mock tools for a reliable live demo."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any]
    error: str | None = None


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_runbook",
            "description": "Search internal runbooks for symptoms, error codes, or service names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_logs",
            "description": "Query recent application logs for a service within a time window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "minutes": {"type": "integer", "description": "Lookback in minutes"},
                    "level": {
                        "type": "string",
                        "enum": ["info", "warn", "error"],
                        "description": "Minimum log level",
                    },
                },
                "required": ["service", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_service_health",
            "description": "Fetch current health, latency p95, and error rate for a service.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_deployments",
            "description": "List recent deployments for a service in the last N hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "hours": {"type": "integer"},
                },
                "required": ["service", "hours"],
            },
        },
    },
]

RUNBOOKS = {
    "api latency": {
        "title": "API latency spike",
        "steps": [
            "Check p95 latency and error rate in the last 15 minutes.",
            "Correlate with recent deploys within 2 hours.",
            "Inspect DB connection pool saturation and slow query logs.",
        ],
    },
    "checkout": {
        "title": "Checkout failures",
        "steps": [
            "Verify payment-gateway health and webhook backlog.",
            "Check cart-service error logs for 5xx spikes.",
        ],
    },
    "deploy": {
        "title": "Post-deploy regression",
        "steps": [
            "Compare error rate before vs after deploy.",
            "Roll back if error rate > 2x baseline for 10+ minutes.",
        ],
    },
}

MOCK_LOGS = {
    "checkout-api": [
        {"ts": "2026-05-20T14:01:12Z", "level": "error", "msg": "payment_gateway timeout after 30s"},
        {"ts": "2026-05-20T14:01:45Z", "level": "error", "msg": "checkout failed order_id=ord_9281"},
        {"ts": "2026-05-20T14:02:03Z", "level": "warn", "msg": "retry attempt 2/3 for payment charge"},
    ],
    "api-gateway": [
        {"ts": "2026-05-20T13:58:00Z", "level": "warn", "msg": "upstream checkout-api latency p95=4200ms"},
        {"ts": "2026-05-20T13:59:10Z", "level": "error", "msg": "circuit breaker open for checkout-api"},
    ],
}

MOCK_HEALTH = {
    "checkout-api": {"status": "degraded", "p95_ms": 4100, "error_rate": 0.12},
    "api-gateway": {"status": "healthy", "p95_ms": 45, "error_rate": 0.001},
    "payment-gateway": {"status": "degraded", "p95_ms": 2800, "error_rate": 0.08},
}

MOCK_DEPLOYS = {
    "checkout-api": [
        {"version": "v2.14.0", "at": "2026-05-20T12:45:00Z", "author": "ci-bot"},
    ],
}


def _simulate_latency() -> None:
    time.sleep(0.15)


def search_runbook(query: str) -> ToolResult:
    _simulate_latency()
    q = query.lower()
    hits = [
        {"id": k, **v}
        for k, v in RUNBOOKS.items()
        if any(term in q for term in k.split()) or k in q or q in k
    ]
    if not hits:
        for key, val in RUNBOOKS.items():
            if any(word in q for word in key.split()):
                hits.append({"id": key, **val})
    if not hits:
        hits = [{"id": "api latency", **RUNBOOKS["api latency"]}]
    return ToolResult(ok=True, data={"query": query, "results": hits[:2]})


def query_logs(service: str, minutes: int, level: str = "warn") -> ToolResult:
    _simulate_latency()
    logs = MOCK_LOGS.get(service, [])
    levels = {"info": 0, "warn": 1, "error": 2}
    min_level = levels.get(level, 1)
    filtered = [row for row in logs if levels.get(row["level"], 0) >= min_level]
    return ToolResult(
        ok=True,
        data={"service": service, "minutes": minutes, "level": level, "entries": filtered},
    )


def check_service_health(service: str) -> ToolResult:
    _simulate_latency()
    health = MOCK_HEALTH.get(service)
    if not health:
        return ToolResult(ok=False, data={}, error=f"Unknown service: {service}")
    return ToolResult(ok=True, data={"service": service, **health})


def get_recent_deployments(service: str, hours: int) -> ToolResult:
    _simulate_latency()
    deploys = MOCK_DEPLOYS.get(service, [])
    return ToolResult(
        ok=True,
        data={"service": service, "hours": hours, "deployments": deploys},
    )


HANDLERS: dict[str, Callable[..., ToolResult]] = {
    "search_runbook": search_runbook,
    "query_logs": query_logs,
    "check_service_health": check_service_health,
    "get_recent_deployments": get_recent_deployments,
}


def execute_tool(name: str, arguments: dict[str, Any], *, fail_once: set[str] | None = None) -> ToolResult:
    """Run a tool with optional injected failure for demoing retries."""
    if fail_once and name in fail_once:
        fail_once.discard(name)
        return ToolResult(ok=False, data={}, error=f"Transient failure calling {name}")

    handler = HANDLERS.get(name)
    if not handler:
        return ToolResult(ok=False, data={}, error=f"Unknown tool: {name}")

    try:
        return handler(**arguments)
    except TypeError as exc:
        return ToolResult(ok=False, data={}, error=str(exc))


def format_tool_result(result: ToolResult) -> str:
    payload = {"ok": result.ok, "data": result.data}
    if result.error:
        payload["error"] = result.error
    return json.dumps(payload, indent=2)
