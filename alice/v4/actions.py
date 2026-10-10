"""The action selector (spec §6.6, T56): what happens to a thought's proposals. No model.

- intention, question, resolve: applied as in V3;
- write: sent only if the user is in the coalition (or an intention due now made the thought), urgency before the
  reset exceeded the brake by a margin (speech has its own, higher threshold), and V3's initiative rules allow it (without V3's
  quiet period after a conversation: InitiativeV4).
  Otherwise the draft becomes an intention "tell the user" with unfinishedness 1, which can grow and come back later
  (T41), and the blocked action adds frustration.
"""

from dataclasses import replace
from datetime import datetime

from ..common.llm import as_int, as_list
from ..v3.initiative import Initiative
from . import constants as K
from .substrate import Event


class InitiativeV4(Initiative):
    """V3's rules for writing first, without V3's quiet period after a conversation while the gate decides when to
    speak: the speech threshold, the conversation mode (30 min) and the daily cap are V4's own brakes (decision
    2026-10-10, tuning log entry 4). With the gate off, V3's rules hold unchanged."""

    def __init__(self, agent, cfg):
        super().__init__(agent, cfg)
        self._v3_cfg, self._v4_cfg = cfg, replace(cfg, quiet_after_hours=0)

    def blocked(self, now: datetime, due: bool = False) -> str | None:
        self.cfg = self._v4_cfg if self.agent.field_on and self.agent.v4_switches.gate else self._v3_cfg
        return super().blocked(now, due)


class ActionSelector:
    def __init__(self, agent):
        self.agent = agent

    def may_speak(self, ev: Event) -> tuple[bool, str]:
        a = self.agent
        f = a.substrate.field
        user = f.special("user")
        if not ev.due and (user is None or user not in ev.coalition):
            return False, "the user is not on its mind"
        r = ev.reading
        if r is None or r.urgency < r.brake * (1 + K.SPEECH_MARGIN):
            return False, "not urgent enough to speak"
        if blocked := a.initiative.blocked(a.clock.now(), due=bool(ev.due)):
            return False, blocked
        return True, ""

    def apply(self, data: dict, ev: Event, wake_id: int) -> tuple[bool, list[dict], list[dict]]:
        """Returns (changed state, messages written first, decisions)."""
        a = self.agent
        changed, written, decisions = False, [], []
        due_ids = a.substrate_due_ids(ev.due)
        for d in as_list(data.get("proposals"), dict)[:6]:
            kind, done, note = d.get("type"), False, ""
            if kind == "intention" and a._later_on():
                done = a.later.add(str(d.get("content") or ""), due=d.get("due"), source="wake") is not None
            elif kind == "question":
                done = a.thoughts.ask(str(d.get("content") or ""), source="wake", source_id=wake_id) is not None
            elif kind == "resolve":
                if (qid := as_int(d.get("question_id"))) is not None:
                    done = a.thoughts.resolve(qid, str(d.get("answer") or ""))
                elif (iid := as_int(d.get("intention_id"))) is not None and a.later.get(iid):
                    a.later.drop(iid, str(d.get("reason") or "dropped on reflection"))
                    done = True
            elif kind == "write":
                content = str(d.get("content") or "").strip()
                ok, note = self.may_speak(ev)
                if ok and content and (msg := a.initiative.write(content, wake_id=wake_id,
                                                                  intention_id=due_ids[0] if due_ids else None)):
                    written.append(msg)
                    done = True
                elif content:   # kept in mind instead: it can come back
                    a.substrate.drives.pulse("frustration", K.FRUSTRATION_BLOCKED)
                    if a._later_on():
                        a.later.add(f"Tell the user: {content}", source="wake")
                    note = note or "not sent"
            decisions.append({**d, "applied": bool(done), **({"note": note} if note else {})})
            changed = changed or bool(done)
        return changed, written, decisions
