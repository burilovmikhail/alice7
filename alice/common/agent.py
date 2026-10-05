"""The protocol every version (V1..V4) and baseline implements, so the eval harness is shared."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from .trace import Tracer


@runtime_checkable
class Agent(Protocol):
    name: str
    tracer: Tracer

    def reply(self, text: str) -> str: ...

    def end_session(self) -> None: ...

    def snapshot(self, path: Path) -> None: ...

    def close(self) -> None: ...

    def last_context_ids(self) -> list[int]:
        """Memory ids shown to the model when the last reply was written ([] for baselines)."""
        ...
