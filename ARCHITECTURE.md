# Architecture — Ops Incident Agent

## Overview

A **ReAct-style** agent that investigates production incidents using **function calling** (tool use), **multi-step reasoning**, and **autonomous tool selection** (live mode).

```
┌─────────────┐     incident      ┌──────────────┐
│   CLI /     │ ───────────────►  │  AgentState  │
│   main.py   │                   │  (messages)  │
└─────────────┘                   └──────┬───────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │              OpsAgent.run()              │
                    │  loop (max 8):                           │
                    │    LLM → tool call OR final answer       │
                    │    execute_tool → observation → history  │
                    └────────────────────┬────────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
     search_runbook              query_logs                 check_service_health
              │                          │                          │
              └──────────────────────────┴──────────────────────────┘
                                         │
                              get_recent_deployments
```

## Components

| File | Responsibility |
|------|----------------|
| `src/main.py` | CLI, Rich trace rendering |
| `src/incidents.py` | Load scenarios from `incidents.json` |
| `incidents.json` | Canned incident scenarios |
| `src/agent.py` | ReAct loop, LLM calls, retry logic |
| `src/tools.py` | Tool schemas + mock implementations |
| `src/state.py` | Session messages + trace steps |
| `src/prompts.py` | System prompt + offline script |
| `tests/test_golden_path.py` | Eval / regression |

## Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Live | `OPENAI_API_KEY` set | OpenAI chooses tools dynamically |
| Offline | `--offline` or `DEMO_OFFLINE=1` | Fixed script, no API |
| Failure inject | `--inject-failure` | First `query_logs` fails once |

## Guardrails

- `MAX_STEPS = 8` — prevents runaway loops
- `MAX_TOOL_RETRIES = 2` — handles transient tool errors
- Allow-listed tools only (no arbitrary code execution)
- Final answer schema enforced via system prompt

## Production extensions (discussion fodder)

- Replace mocks with real observability APIs (scoped API tokens)
- Persist `AgentState` to Redis for async human approval
- Add eval harness: expected tools + structured output validation
- OTEL spans per step for latency/cost dashboards
