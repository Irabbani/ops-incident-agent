"""ReAct-style ops agent with tool use, retries, and offline demo mode."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from prompts import OFFLINE_FINAL, OFFLINE_SCRIPT, SYSTEM_PROMPT
from state import AgentState
from tools import TOOL_SCHEMAS, execute_tool, format_tool_result


MAX_STEPS = 8
MAX_TOOL_RETRIES = 2


class OpsAgent:
    def __init__(self, *, offline: bool = False, inject_failure: bool = False) -> None:
        self.offline = offline or os.getenv("DEMO_OFFLINE", "0") == "1"
        self.inject_failure = inject_failure
        self._fail_once: set[str] = {"query_logs"} if inject_failure else set()
        self._offline_idx = 0
        self.client = None if self.offline else OpenAI()

    def run(self, incident: str) -> AgentState:
        state = AgentState(incident=incident)
        state.add_message("system", SYSTEM_PROMPT)
        state.add_message("user", f"Incident report:\n{incident}")

        for step in range(MAX_STEPS):
            if self.offline:
                decision = self._offline_decision(state)
            else:
                decision = self._llm_decision(state)

            if decision["type"] == "final":
                state.record_step("answer", decision["content"])
                state.add_message("assistant", decision["content"])
                return state

            self._run_tool_step(state, decision)

        state.record_step(
            "answer",
            "Stopped: max steps reached. Escalate to human on-call with collected evidence.",
        )
        return state

    def _offline_decision(self, state: AgentState) -> dict[str, Any]:
        if self._offline_idx >= len(OFFLINE_SCRIPT):
            return {"type": "final", "content": OFFLINE_FINAL}

        script = OFFLINE_SCRIPT[self._offline_idx]
        self._offline_idx += 1
        state.record_step("thought", script["thought"])
        return {
            "type": "tool",
            "name": script["tool"],
            "arguments": script["args"],
            "thought": script["thought"],
        }

    def _llm_decision(self, state: AgentState) -> dict[str, Any]:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = self.client.chat.completions.create(
            model=model,
            messages=state.messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            call = msg.tool_calls[0]
            args = json.loads(call.function.arguments or "{}")
            thought = (msg.content or "").strip() or f"Calling {call.function.name}"
            state.record_step("thought", thought)
            state.add_message(
                "assistant",
                content=msg.content,
                tool_calls=[
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                ],
            )
            return {
                "type": "tool",
                "name": call.function.name,
                "arguments": args,
                "tool_call_id": call.id,
                "thought": thought,
            }

        content = (msg.content or "").strip()
        state.record_step("thought", "Producing final answer from gathered evidence.")
        return {"type": "final", "content": content}

    def _run_tool_step(self, state: AgentState, decision: dict[str, Any]) -> None:
        name = decision["name"]
        args = decision["arguments"]
        tool_call_id = decision.get("tool_call_id", f"call_{state.tool_calls}")

        attempt = 0
        result = execute_tool(name, args, fail_once=self._fail_once)

        while not result.ok and attempt < MAX_TOOL_RETRIES:
            attempt += 1
            state.retries += 1
            state.record_step(
                "retry",
                f"{name} failed ({result.error}); retry {attempt}/{MAX_TOOL_RETRIES}",
            )
            result = execute_tool(name, args, fail_once=None)

        state.tool_calls += 1
        observation = format_tool_result(result)
        state.record_step(
            "action",
            f"{name}({json.dumps(args)})",
            tool=name,
            arguments=args,
        )
        state.record_step("observation", observation, tool=name, ok=result.ok)

        state.add_message(
            "tool",
            observation,
            tool_call_id=tool_call_id,
            name=name,
        )
