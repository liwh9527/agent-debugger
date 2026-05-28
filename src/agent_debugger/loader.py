"""Load AgentTrace from JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from agent_debugger.schema import AgentTrace


def load_trace(path: str | Path) -> AgentTrace:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")
    if not path.suffix == ".json":
        raise ValueError(f"Expected .json file, got: {path.suffix}")
    with open(path) as f:
        data = json.load(f)
    return AgentTrace.model_validate(data)
