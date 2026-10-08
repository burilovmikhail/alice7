"""V2 context: V1's system prompt and <memory> block, plus sections contributed by V2 mechanisms.

With no sections (every switch off, or no state yet) the text is exactly V1's. The persona file stays
byte-identical; each V2 section carries its own one-line framing instead (spec §6.7)."""

from dataclasses import dataclass, field
from typing import Protocol

from ..common.config import Config
from ..common.clock import Clock
from ..v1.context import ContextBuilder, MemoryBlock, SystemPrompt
from ..v1.session import Session
from ..v1.store import MemoryStore

TODAY_MARK = "\n\nToday: "  # V1 always ends the system prompt with the date; V2 sections go before it


@dataclass
class Section:
    title: str                 # fixed string, e.g. "## Who you are — in your own words"
    body: str
    framing: str = ""          # one line saying what this section is and where it came from
    shown: dict = field(default_factory=dict)   # what was shown, for turn_state: {"lesson_ids": [...]}

    def render(self) -> str:
        return "\n".join(p for p in (self.title, self.framing, self.body) if p)


class Mechanism(Protocol):
    """A V2 mechanism that contributes to the context. Either method may return None."""

    def system_section(self) -> Section | None: ...

    def memory_section(self, query: str, session: Session) -> Section | None: ...


class ContextV2(ContextBuilder):
    def __init__(self, store: MemoryStore, cfg: Config, clock: Clock, persona: str, mechanisms=lambda: []):
        """`mechanisms()` returns the mechanisms that are switched on right now."""
        super().__init__(store, cfg, clock, persona)
        self.mechanisms = mechanisms
        self.shown: dict = {}

    def begin_turn(self) -> None:
        self.shown = {}

    def _record(self, section: Section) -> None:
        for key, value in section.shown.items():
            if isinstance(value, list):
                self.shown.setdefault(key, []).extend(v for v in value if v not in self.shown.get(key, []))
            else:
                self.shown[key] = value

    def system_prompt(self) -> SystemPrompt:
        base = super().system_prompt()
        sections = [s for m in self.mechanisms() if (s := m.system_section()) is not None]
        if not sections:
            return base
        for s in sections:
            self._record(s)
        head, mark, date = base.text.rpartition(TODAY_MARK)
        if not mark:  # V1 changed its layout: fail loudly rather than silently misplace sections
            raise RuntimeError("V1 system prompt no longer ends with the date line")
        text = "\n\n".join([head, *(s.render() for s in sections)]) + mark + date
        return SystemPrompt(text, base.core_ids)

    def memory_block(self, query: str, session: Session) -> MemoryBlock:
        base = super().memory_block(query, session)
        sections = [s for m in self.mechanisms() if (s := m.memory_section(query, session)) is not None]
        if not sections:
            return base
        for s in sections:
            self._record(s)
        text = "\n\n".join([base.text, *(s.render() for s in sections)]) if base.text else \
            "\n\n".join(s.render() for s in sections)
        return MemoryBlock(text, base.shown_ids, base.result)
