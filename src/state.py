"""Session state for multi-turn agent context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    incident: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0
    retries: int = 0

    def record_step(self, kind: str, content: str, **extra: Any) -> None:
        entry = {"kind": kind, "content": content, **extra}
        self.steps.append(entry)

    def add_message(self, role: str, content: str | None = None, **kwargs: Any) -> None:
        msg: dict[str, Any] = {"role": role}
        if content is not None:
            msg["content"] = content
        msg.update(kwargs)
        self.messages.append(msg)
