"""CLI entrypoint for the Ops Incident Agent demo."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

# Allow `python src/main.py` without installing as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import OpsAgent  # noqa: E402
from incidents import load_incidents  # noqa: E402


def render_trace(console: Console, state) -> None:
    for i, step in enumerate(state.steps, start=1):
        kind = step["kind"]
        content = step["content"]
        if kind == "thought":
            console.print(Panel(content, title=f"Step {i} · Thought", border_style="cyan"))
        elif kind == "action":
            console.print(Panel(content, title=f"Step {i} · Action", border_style="yellow"))
        elif kind == "observation":
            style = "green" if step.get("ok", True) else "red"
            console.print(Panel(content, title=f"Step {i} · Observation", border_style=style))
        elif kind == "retry":
            console.print(Panel(content, title=f"Step {i} · Retry", border_style="magenta"))
        elif kind == "answer":
            console.print(Rule("[bold]Final answer[/bold]"))
            console.print(Markdown(content))


def render_stats(console: Console, state) -> None:
    table = Table(title="Run metrics", show_header=True)
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Tool calls", str(state.tool_calls))
    table.add_row("Retries", str(state.retries))
    table.add_row("Trace steps", str(len(state.steps)))
    console.print(table)


def main() -> int:
    load_dotenv()

    try:
        incidents = load_incidents()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to load incidents: {exc}", file=sys.stderr)
        return 1

    default_scenario = next(iter(incidents))

    parser = argparse.ArgumentParser(description="Ops Incident Agent — interview demo")
    parser.add_argument(
        "--scenario",
        choices=list(incidents.keys()),
        default=default_scenario,
        help="Scenario key from incidents.json",
    )
    parser.add_argument("--incident", help="Custom incident text (overrides scenario)")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Deterministic scripted run (no API key)",
    )
    parser.add_argument(
        "--inject-failure",
        action="store_true",
        help="Simulate one transient tool failure to demo retry logic",
    )
    args = parser.parse_args()
    incident = args.incident or incidents[args.scenario]
    offline = args.offline or os.getenv("DEMO_OFFLINE", "0") == "1"

    if not offline and not os.getenv("OPENAI_API_KEY"):
        print(
            "No OPENAI_API_KEY found. Use --offline for a dry run, or copy .env.example to .env.",
            file=sys.stderr,
        )
        return 1

    console = Console()
    mode = "offline (scripted)" if offline else "live (LLM + tools)"
    console.print(
        Panel(
            f"[bold]Ops Incident Agent[/bold]\nMode: {mode}\n\n{incident}",
            title="Incident",
            border_style="blue",
        )
    )

    agent = OpsAgent(offline=offline, inject_failure=args.inject_failure)
    state = agent.run(incident)
    render_trace(console, state)
    render_stats(console, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
