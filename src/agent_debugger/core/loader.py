"""Load AgentTrace from JSON files or external formats via adapters."""

from __future__ import annotations

import json
from pathlib import Path

from agent_debugger.core.schema import AgentTrace


def load_trace(path: str | Path) -> AgentTrace:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    if path.suffix == ".json":
        return _load_native_json(path)

    adapter = _detect_adapter(path)
    if adapter:
        return adapter.load(path)

    raise ValueError(f"Unsupported file format: {path.suffix}")


def _load_native_json(path: Path) -> AgentTrace:
    with open(path) as f:
        data = json.load(f)
    return AgentTrace.model_validate(data)


def _detect_adapter(path: Path):
    from agent_debugger.adapters import ADAPTERS

    for adapter in ADAPTERS:
        if adapter.detect(path):
            return adapter
    return None
