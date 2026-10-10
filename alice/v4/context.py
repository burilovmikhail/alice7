"""V4's context for a reply (spec §6.11): V3's, with sections replaced where a switch says so.

| section                                   | source                                                     |
| persona, "Your own time"                  | V3, unchanged                                              |
| how you are                               | mood and salient drives in words (switch `drives`)         |
| what you believe about yourself (a guess) | the narrative (switch `narrative`, narrative.py)           |
| on your mind                              | working memory, labelled by kind (intentions, own thoughts) |
| from experience with the user             | traces (switch `traces`, traces.py)                        |
| what you remember                         | recall by activation (switch `recall`, recall.py)          |

No lessons, no habits. What is shown was chosen by the field before the reply (AgentV4._turn).
"""

import json
from datetime import datetime

from ..common.text import estimate_tokens
from ..common.timefmt import ago
from ..v1.context import MemoryBlock
from ..v1.retrieval import search
from ..common.timeparse import parse_time_range
from ..v1.session import Session
from ..v2.context import ContextV2, Section
from . import constants as K

HOW_TITLE = "## How you are"
HOW_FRAMING = "How you feel right now, carried over from what has been happening; not something to report."
MIND_TITLE = "## On your mind"
MIND_FRAMING = ("What is on your mind right now, as it came up by itself: things you meant to do, your own earlier "
                "thoughts, things that happened.")
WOKE_TITLE = "## Waking up"
WOKE_FRAMING = "How your night went."
WOKE_KEY = "v4_woke_with"


class ContextV4(ContextV2):
    """V1's <memory> block with V1's search swapped for recall by activation; the rest is ContextV2's."""

    def __init__(self, agent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent

    def time_block(self, session: Session, now: datetime) -> str:
        text = super().time_block(session, now)
        if self.agent._ablated("episodic"):   # E15: no session summaries either
            text = "\n".join(line for line in text.split("\n") if not line.startswith("Previous conversation:"))
        return text

    def _base_block(self, query: str, session: Session) -> MemoryBlock:
        """V1's memory_block (v1/context.py), with the hits from recall when the switch is on."""
        a = self.agent
        now = self.clock.now()
        if a.v4_switches.on("recall") and a._turn.get("recall") is not None:
            result = a._turn["recall"]
        else:
            result = search(self.store, query, now=now, date_range=parse_time_range(query, now.date()))
            if a._ablated("episodic"):
                result.hits = [h for h in result.hits if h.memory.kind != "episode"]
        budget = self.cfg.retrieval_budget
        lines, shown_ids = [], []
        listed = {h.memory.id for h in result.hits}
        for i, hit in enumerate(result.hits):
            line, cause_ids = self._render(hit.memory, now, i < 3, listed)
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
                     for s, rel, d in self.store.entity_relations(entity_ids)][:15]
        sections = [self.time_block(session, now)]
        if lines:
            sections.append("## Possibly relevant\n" + "\n".join(lines))
        if relations:
            sections.append("## Relations\n" + "\n".join(relations))
        if session.summary:
            sections.append("## Earlier in this conversation\n" + session.summary)
        return MemoryBlock("\n\n".join(sections), shown_ids, result)

    def memory_block(self, query: str, session: Session) -> MemoryBlock:
        if not self.agent.v4_switches.field:
            return super().memory_block(query, session)
        base = self._base_block(query, session)
        sections = [s for m in self.mechanisms() if (s := m.memory_section(query, session)) is not None]
        for s in sections:
            self._record(s)
        if not sections:
            return base
        text = "\n\n".join([base.text, *(s.render() for s in sections)]) if base.text else \
            "\n\n".join(s.render() for s in sections)
        return MemoryBlock(text, base.shown_ids, base.result)


class HowYouAreMechanism:
    """Mood and the drives far from baseline, in words (D7), in place of V3's mood section."""

    def __init__(self, agent):
        self.agent = agent

    def system_section(self) -> Section | None:
        a = self.agent
        return Section(HOW_TITLE, a.substrate.drives.words(a._silence_seconds()), HOW_FRAMING)

    def memory_section(self, query: str, session: Session) -> Section | None:
        return None


class WorkingMemoryMechanism:
    """Working memory at the moment of the reply, each item labelled by kind (spec §6.6, §6.11)."""

    def __init__(self, agent):
        self.agent = agent

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        a = self.agent
        f = a.substrate.field
        now = a.clock.now()
        t = a.substrate.t or 0.0
        recalled = {h.memory.id for h in (a._turn.get("recall").hits if a._turn.get("recall") else [])}
        lines, shown = [], []
        for i in a._turn.get("wm") or []:
            kind = f.kind[i]
            if kind in ("user", "self", "trace") or not f.alive[i]:
                continue
            if kind in ("memory", "episode") and (f.ref[i] in recalled or
                                                  (kind == "episode" and a._ablated("episodic"))):
                continue
            if kind == "intention":
                it = a.later.get(f.ref[i]) if a._later_on() else None
                if it is None or it.status != "open":
                    continue
                lines.append(f"- [#{it.id}] {it.content} (something you meant to do, since {ago(it.created_at, now)}"
                             + (f", for {it.due}" if it.due else "") + ")")
                shown.append(int(f.ids[i]))
                continue
            lines.append(f"- ({f.describe(i, t)}) {f.label[i][:400]}")
            shown.append(int(f.ids[i]))
        if not lines:
            return None
        return Section(MIND_TITLE, "\n".join(lines), MIND_FRAMING, {"wm": shown})


class WokeMechanism:
    """The first reply after waking: how long the agent slept, its dreams, what was on its mind (spec §6.10)."""

    def __init__(self, agent):
        self.agent = agent

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        a = self.agent
        raw = a.db.execute("SELECT value FROM meta WHERE key=?", (WOKE_KEY,)).fetchone()
        if not raw or a.store.message_count(session.id) >= 2:
            return None
        woke = json.loads(raw[0])
        last_user = a.db.execute("SELECT MAX(ts) FROM messages WHERE role='user' AND session_id != ?",
                                 (session.id,)).fetchone()[0]
        if last_user and last_user > woke["at"]:
            return None   # already talked since
        now = a.clock.now()
        lines = [f"You woke up {ago(woke['at'], now)}" + (f", after about {round(woke['slept_hours'])} hours of sleep."
                                                           if woke.get("slept_hours") else ".")]
        for d in woke.get("dreams", [])[:K.DREAMS_PER_NIGHT]:
            lines.append(f"You dreamt: {d}")
        if woke.get("on_mind"):
            lines.append("On your mind when you woke: " + "; ".join(woke["on_mind"]))
        return Section(WOKE_TITLE, " ".join(lines), WOKE_FRAMING)
