"""Base adapter interface for converting external trace formats to AgentTrace."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from agent_debugger.core.schema import AgentTrace


class BaseAdapter(ABC):
    name: str = "unknown"

    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return True if this adapter can handle the given file."""

    @abstractmethod
    def load(self, path: Path) -> AgentTrace:
        """Load and convert the file into an AgentTrace."""
