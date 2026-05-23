SYSTEM_PROMPT = """You are an on-call operations agent that investigates production incidents.

Rules:
- Think step by step. Use tools before concluding.
- Call at most one tool per turn.
- Prefer: runbook search → health checks → logs → deploy history.
- When you have enough evidence, respond with a final answer (no tool call).
- Final answer must include: root cause hypothesis, confidence (low/medium/high), and 2-3 concrete next actions.

Available services in this environment: checkout-api, api-gateway, payment-gateway.
"""

OFFLINE_SCRIPT = [
    {
        "tool": "search_runbook",
        "args": {"query": "checkout payment timeout"},
        "thought": "Customer reports checkout failures — I'll search the runbook first.",
    },
    {
        "tool": "check_service_health",
        "args": {"service": "checkout-api"},
        "thought": "Runbook points to latency — checking checkout-api health.",
    },
    {
        "tool": "query_logs",
        "args": {"service": "checkout-api", "minutes": 30, "level": "error"},
        "thought": "Service is degraded with high error rate — pulling error logs.",
    },
    {
        "tool": "get_recent_deployments",
        "args": {"service": "checkout-api", "hours": 4},
        "thought": "Logs show payment gateway timeouts — checking for a recent deploy.",
    },
]

OFFLINE_FINAL = """## Incident summary

**Hypothesis:** Checkout failures are driven by **payment-gateway timeouts**, surfaced as degraded `checkout-api` with 12% error rate and p95 ~4.1s. A deploy (`v2.14.0` ~90m ago) may have changed timeout/retry behavior.

**Confidence:** medium — health and logs align; payment-gateway is also degraded.

**Recommended actions**
1. Fail over or scale payment-gateway; confirm vendor status page.
2. Temporarily increase checkout payment timeout if safe; watch circuit breaker on api-gateway.
3. If error rate stays >2× baseline 10+ min post-mitigation, roll back `checkout-api` v2.14.0.

**Limitations:** Mock telemetry only; no live paging or change-management integration in this demo.
"""
