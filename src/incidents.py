"""Load incident scenarios from incidents.json."""

from __future__ import annotations

import json
from pathlib import Path

INCIDENTS_PATH = Path(__file__).resolve().parents[1] / "incidents.json"


def load_incidents(path: Path | None = None) -> dict[str, str]:
    """Return scenario name -> incident text from a flat JSON object."""
    incidents_path = path or INCIDENTS_PATH
    if not incidents_path.is_file():
        raise FileNotFoundError(f"Incidents file not found: {incidents_path}")

    with incidents_path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or not data:
        raise ValueError(f"{incidents_path}: expected a non-empty JSON object")

    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(f"{incidents_path}: each entry must be a string key and string value")

    return data
