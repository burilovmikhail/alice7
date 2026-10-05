"""Context assembly: the stable part (persona + core facts + date) and the per-turn <memory> block."""

from dataclasses import dataclass, field
from datetime import datetime

from ..common.clock import Clock
from ..common.config import Config
from ..common.text import WEEKDAYS, estimate_tokens, short, today_human
from ..common.timefmt import ago, duration, part_of_day
from ..common.timeparse import parse_time_range
from .retrieval import SearchResult, search
from .session import Session
from .store import Memory, MemoryStore

RETURN_GAP_MINUTES = 30   # a pause inside a conversation worth noticing
EARLY_MESSAGES = 4        # look back at the previous session only at the start of a new one
THREAD_TOP = 3            # top hits that also show what they grew out of
MAX_RELATIONS = 15


@dataclass
class SystemPrompt:
    text: str
    core_ids: list[int] = field(default_factory=list)


@dataclass
class MemoryBlock:
    text: str | None
    shown_ids: list[int]          # retrieved memories (and their causes) that made it into the block
    result: SearchResult


class ContextBuilder:
    def __init__(self, store: MemoryStore, cfg: Config, clock: Clock, persona: str):
        self.store, self.cfg, self.clock, self.persona = store, cfg, clock, persona

    def system_prompt(self) -> SystemPrompt:
        """Changes rarely (day granularity) — cache-friendly."""
        parts = [self.persona]
        core, ids, used = [], [], 0
        for m in self.store.core_memories():
            used += estimate_tokens(m.content)
            if used > self.cfg.core_budget:
                break
            core.append(f"- {m.content}")
            ids.append(m.id)
        if core:
            parts.append("## What you know for sure about the user\n" + "\n".join(core))
        else:
            parts.append("## You don't know anything about the user yet.")
        parts.append(f"Today: {today_human(self.clock.now().date())}.")
        return SystemPrompt("\n\n".join(parts), ids)

    def time_block(self, session: Session, now: datetime) -> str:
        lines = [f"Now: {WEEKDAYS[now.weekday()]}, {now:%Y-%m-%d %H:%M} ({part_of_day(now.hour)})."]
        info = self.store.session_info(session.id)
        last = self.store.last_message(session.id)
        if last:
            gap = (now - datetime.fromisoformat(last["ts"])).total_seconds()
            if gap > RETURN_GAP_MINUTES * 60:
                lines.append(f"The user is back after a pause of {duration(gap)}.")
            running = (now - datetime.fromisoformat(info["started_at"])).total_seconds()
            if running > 5 * 60:
                lines.append(f"This conversation has been going on for {duration(running)}.")
        count = self.store.message_count(session.id)
        if count < EARLY_MESSAGES:
            first, sessions = self.store.acquaintance()
            if first:
                n = sessions + (0 if count else 1)
                lines.append(f"You've known each other since {first[:10]} ({ago(first, now)}); "
                             f"this is conversation #{n}.")
            else:
                lines.append("This is your first conversation with the user.")
            if prev := self.store.previous_session(session.id):
                summary = (prev["summary"] or "").strip()
                lines.append(f"Previous conversation: {ago(prev['last_ts'], now)}"
                             + (f". {short(summary, 400)}" if summary else "."))
        return "## Time\n" + "\n".join(lines)

    def _render(self, m: Memory, now: datetime, with_thread: bool, shown: set[int]) -> tuple[str, list[int]]:
        line = f"- [#{m.id}, {ago(m.valid_from, now)}] {m.content}"
        causes: list[Memory] = []
        if with_thread:
            causes = [c for c in self.store.causes(m.id) if c.id not in shown][:2]
            if causes:
                line += "\n  ↳ grew out of: " + "; ".join(
                    f"#{c.id} ({ago(c.valid_from, now)}) «{short(c.content)}»" for c in causes)
        return line, [c.id for c in causes]

    def memory_block(self, query: str, session: Session) -> MemoryBlock:
        """Memories relevant to the current message, within the token budget. Doesn't touch anything:
        the agent touches the shown ids once the reply has actually been produced."""
        now = self.clock.now()
        result = search(self.store, query, now=now, date_range=parse_time_range(query, now.date()))
        budget = self.cfg.retrieval_budget
        lines, shown_ids = [], []
        listed = {h.memory.id for h in result.hits}
        for i, hit in enumerate(result.hits):
            line, cause_ids = self._render(hit.memory, now, i < THREAD_TOP, listed)
            cost = estimate_tokens(line)
            if cost > budget:
                break
            budget -= cost
            hit.in_prompt = True
            lines.append(line)
            shown_ids.append(hit.memory.id)
            shown_ids.extend(c for c in cause_ids if c not in shown_ids)

        entity_ids = {e.id for e in self.store.entities_in_text(query)}
        entity_ids |= set(self.store.memory_entity_ids(shown_ids))
        entity_ids -= {self.store.user_id, self.store.self_id}
        relations = [f"- {self.store.entity_label(s)} — {rel} — {self.store.entity_label(d)}"
                     for s, rel, d in self.store.entity_relations(entity_ids)][:MAX_RELATIONS]

        sections = [self.time_block(session, now)]
        if lines:
            sections.append("## Possibly relevant\n" + "\n".join(lines))
        if relations:
            sections.append("## Relations\n" + "\n".join(relations))
        if session.summary:
            sections.append("## Earlier in this conversation\n" + session.summary)
        return MemoryBlock("\n\n".join(sections), shown_ids, result)
