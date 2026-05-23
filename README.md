# Ops Incident Agent — Interview Demo

A **multi-step AI agent** for on-call incident triage: tool use, ReAct loop, retries, offline CI mode, and golden-path tests.



## Quick start

```powershell
git clone https://github.com/Irabbani/ops-incident-agent.git
cd ops-incident-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Reliable demo (no API key)
python src\main.py --offline

# Live LLM (needs .env)
copy .env.example .env
python src\main.py --scenario checkout

# Show retry handling
python src\main.py --offline --inject-failure
```

## What makes this "more than one LLM call"

1. **Tool use** — runbook search, logs, health, deploy history  
2. **Multi-step reasoning** — up to 8 plan → act → observe cycles  
3. **Autonomous decisions** — live mode picks which tool to call next  


## Tests

```powershell
pip install pytest
pytest tests/test_golden_path.py -q
```

## Scenarios

Canned incidents live in **[incidents.json](incidents.json)** — a flat JSON object (`"scenario-name": "incident text"`). The first entry is the CLI default.

| Flag | Description |
|------|-------------|
| `--scenario checkout` | Payment/checkout failures (default) |
| `--scenario latency` | API latency spike |
| `--incident "..."` | Custom incident text (overrides scenario) |
