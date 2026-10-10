"""The action selector (spec §6.6, T56): what happens to a thought's proposals. No model.

- intention, question, resolve: applied as in V3;
- write: sent only if the user is on its mind (in the coalition, or an intention due now made the thought) and the
  wish to speak clears a threshold (tuning log, entry 5): no daily cap, no quiet period, no awake window, no "the
  last message has no reply yet" while the gate is on; instead shyness (unanswered messages, messages already sent
  today) and night raise the threshold, and the user having the chat open lowers it:

      speech = max u over the last hour / brake + social · a(user) (+ 1 for a due intention)
      need   = 1 + margin + 0.5·unanswered + 0.3·written today + 1·night − 0.6·present

  Otherwise the draft becomes an intention "tell the user" with unfinishedness 1, which can grow and come back later
  (T41), and the blocked action adds frustration. With the gate off, V3's rules hold unchanged.
"""

from datetime import datetime

from ..common.llm import as_int, as_list
from ..v3.initiative import Initiative
from . import constants as K
from .sleep import circadian_at
from .substrate import Event


class InitiativeV4(Initiative):
    """V3's rules for writing first apply only with the gate off; with the gate on the selector's threshold decides
    (decisions 2026-10-10, tuning log entries 4 and 5)."""

    def blocked(self, now: datetime, due: bool = False) -> str | None:
        if self.agent.field_on and self.agent.v4_switches.gate:
            return None if self.agent.v3_switches.initiative else "initiative off"
        return super().blocked(now, due)


class ActionSelector:
    def __init__(self, agent):
        self.agent = agent

    def threshold(self, ev: Event) -> tuple[float, float, dict]:
        """(speech, need, the parts) for a thought: the wish to speak against what it takes."""
        a = self.agent
        s, f, db = a.substrate, a.substrate.field, a.db
        r = ev.reading
        user = f.special("user")
        a_user = float(f.a[user]) if user is not None else 0.0
        peak = max(s.u_peak, r.urgency if r else 0.0)
        speech = (peak / r.brake if r and r.brake > 0 else 0.0) + K.SPEECH_SOCIAL * s.drives.get("social") * a_user \
            + (K.SPEECH_DUE if ev.due else 0.0)
        last_user = db.execute("SELECT COALESCE(MAX(id), 0) FROM messages WHERE role='user'").fetchone()[0]
        unanswered = db.execute("SELECT COUNT(*) FROM outbox WHERE message_id > ?", (last_user,)).fetchone()[0]
        day = a.clock.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        today = db.execute("SELECT COUNT(*) FROM outbox WHERE at >= ?", (day,)).fetchone()[0]
        night = max(0.0, (K.NIGHT_C - circadian_at(s.t)) / K.NIGHT_C)
        present = s.present()
        need = 1 + K.SPEECH_MARGIN + K.SHY_UNANSWERED * unanswered + K.SHY_TODAY * today + K.SPEECH_NIGHT * night \
            - (K.PRESENCE_SPEECH if present else 0.0)
        return speech, need, {"unanswered": unanswered, "today": today, "night": round(night, 2), "present": present}

    def may_speak(self, ev: Event) -> tuple[bool, str]:
        a = self.agent
        f = a.substrate.field
        user = f.special("user")
        if not ev.due and (user is None or user not in ev.coalition):
            return False, "the user is not on its mind"
        if blocked := a.initiative.blocked(a.clock.now(), due=bool(ev.due)):
            return False, blocked
        if a.v4_switches.gate:
            speech, need, parts = self.threshold(ev)
            if speech < need:
                why = ", ".join(f"{k} {v}" for k, v in parts.items() if v)
                return False, f"not enough to speak: {speech:.2f} < {need:.2f}" + (f" ({why})" if why else "")
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
