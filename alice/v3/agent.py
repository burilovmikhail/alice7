"""V3 agent: V2 plus continuous cognition (spec specs/v3/continuous-cognition.md).

AgentV3 subclasses the frozen AgentV2. Silence is lived through `advance(to)`: every session close, stream tick,
pressure check, wake and sleep scheduled between the agent's last event and `to` runs in sim-time order, each at
its own time. With every V3 switch off, advance() does nothing and V3 sends every model exactly what V2 sends."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from ..common.clock import Clock, iso
from ..common.config import Config
from ..common.db import get_meta, set_meta
from ..v1.agent import AgentV1
from ..v1.session import Session
from ..v2.agent import AgentV2
from ..v2.switches import NAMES as V2_NAMES
from . import rhythm
from .affect import Affect, AffectMechanism
from .initiative import Initiative
from .intentions import LaterIntentions, LaterIntentionsMechanism
from .pressure import Monitor
from .stream import Stream
from .thoughts import Thoughts, ThoughtsMechanism
from .turn_observer import TurnObserver
from .wake import Waker
from .config import V3Config, load_v3_config
from .schema import ensure_schema
from .switches import NAMES as V3_NAMES
from .switches import V3Switches

log = logging.getLogger(__name__)

CURSOR = "v3_cursor"          # meta: the sim time silence has been lived up to
LAST_SLEEP = "v3_last_sleep"  # meta: when the last nightly sleep ran
LAST_WAKE = "v3_last_wake"    # meta: when the last wake ran ("fresh" means since then)
DUE_ACTED = "v3_due_acted"    # meta: {"day": ..., "ids": [...]} due intentions a wake has already considered today
MAX_EVENTS = 10_000           # guard against a schedule that never moves forward


class AgentV3(AgentV2):
    name = "V3"

    def __init__(self, cfg: Config, clock: Clock, db_path: Path | str | None = None, *, v3: V3Config | None = None,
                 v3_switches: V3Switches | None = None, **kwargs):
        """v3_switches: explicit build-time V3 switches; otherwise the ones this database was created with, otherwise
        V3Config's. V2's switches work as in V2 (`switches=`)."""
        self.v3 = v3 or load_v3_config()
        self._v3_ready = False
        super().__init__(cfg, clock, db_path, **kwargs)
        ensure_schema(self.db)
        stored = get_meta(self.db, "v3_switches")
        if v3_switches is None:
            v3_switches = V3Switches(**json.loads(stored)) if stored else self.v3.switches
        if stored is None:
            set_meta(self.db, "v3_switches", json.dumps(v3_switches.as_dict()))
        self.v3_switches = v3_switches
        self.v3_models = self.v3.models(cfg)
        self.affect = Affect(self.store)
        self.later = LaterIntentions(self.store, cfg.session_gap_hours)
        self.turn_observer = TurnObserver(self.store, self.affect, self.later, self.llm, self.models["observe"])
        self.thoughts = Thoughts(self.store)
        self.stream = Stream(self.store, self.llm, self.v3_models["stream"], self.affect, self.later, self.thoughts)
        self.monitor = Monitor(self.store, self.affect, self.later, self.thoughts, lambda: self.v3_switches.affect)
        self.initiative = Initiative(self, self.v3)
        self.waker = Waker(self, self.llm, self.v3_models["wake"])
        self._v3_mechanisms = {
            "affect": AffectMechanism(self.affect), "later": LaterIntentionsMechanism(self.later),
            "thoughts": ThoughtsMechanism(self.thoughts, self.stream.latest, lambda: self.v3_switches.stream,
                                          lambda: self.v3_switches.wakes or self.v3_switches.sleep)}
        # With V3 intentions on, V2's self-review no longer makes V2 intentions: wakes and sleep make V3 ones
        review = self._mechanisms["selfmodel"]
        review.switches = lambda: (self.switches.with_({"intentions": False}) if self._later_on() else self.switches)
        self._v3_ready = True

    # ---------- switches ----------

    def _later_on(self) -> bool:
        return self.v3_switches.later and self.switches.intentions

    def active_mechanisms(self) -> list:
        """V2's mechanisms, with V3 intentions in place of V2's, plus the mood."""
        if not getattr(self, "_v3_ready", False):
            return super().active_mechanisms()
        out = []
        for name, m in self._mechanisms.items():
            if not getattr(self.switches, name):
                continue
            out.append(self._v3_mechanisms["later"] if name == "intentions" and self._later_on() else m)
        if self.v3_switches.affect:
            out.append(self._v3_mechanisms["affect"])
        if self.v3_switches.lives_in_silence:
            out.append(self._v3_mechanisms["thoughts"])
        return out

    def apply_switches(self, changes: dict[str, bool]) -> None:
        """Probe-time ablation of V2 and V3 mechanisms alike (forks only)."""
        if unknown := set(changes) - set(V2_NAMES) - set(V3_NAMES):
            raise ValueError(f"unknown switch(es): {', '.join(sorted(unknown))}")
        if v2 := {k: v for k, v in changes.items() if k in V2_NAMES}:
            super().apply_switches(v2)
        if v3 := {k: v for k, v in changes.items() if k in V3_NAMES}:
            self.v3_switches = self.v3_switches.with_(v3)

    def describe(self) -> dict:
        return {**super().describe(), "v3": self.v3.public(self.cfg), "v3_switches": self.v3_switches.as_dict()}

    # ---------- turns ----------

    def _after_turn(self, session: Session) -> None:
        if not getattr(self, "_v3_ready", False) or not (self._later_on() or self.v3_switches.affect
                                                          or self.v3_switches.stream):
            super()._after_turn(session)  # exactly V2
            return
        # V2's steps with its intentions handed over to V3: V1 extraction and fold, V2 reactions and lessons
        AgentV1._after_turn(self, session)
        v2_intentions = self.switches.intentions and not self._later_on()
        if self.switches.lessons or v2_intentions:
            self.observer.observe(session, lessons=self.switches.lessons, intentions=v2_intentions)
            if self.switches.lessons and len(self.lessons.unreflected()) >= self.v2.reflect_every:
                self.reflector.reflect(session_summary=session.summary)
        self.turn_observer.observe(session, affect=self.v3_switches.affect, intentions=self._later_on())
        if self.v3_switches.stream:  # in conversation the stream ticks once per turn, after the reply
            self.stream.tick(rhythm.CONVERSATION)

    # ---------- time ----------

    def _set_time(self, at: datetime) -> None:
        """Events run at their own sim time. With a real clock (interactive chat) they run now."""
        if hasattr(self.clock, "set"):
            self.clock.set(at)

    def _cursor(self) -> datetime:
        stored = get_meta(self.db, CURSOR)
        last = self.db.execute("SELECT MAX(ts) FROM messages").fetchone()[0]
        times = [datetime.fromisoformat(x) for x in (stored, last) if x]
        return max(times) if times else self.clock.now()

    def _session_close_at(self) -> datetime | None:
        if self.session is None:
            return None
        last = self.store.last_message(self.session.id)
        return datetime.fromisoformat(last["ts"]) + timedelta(hours=self.cfg.session_gap_hours) if last else None

    def _something_new_since_sleep(self, t: datetime) -> bool:
        since = get_meta(self.db, LAST_SLEEP) or "0000"
        return bool(self.db.execute("SELECT 1 FROM memories WHERE created_at > ? AND created_at <= ? LIMIT 1",
                                    (since, iso(t))).fetchone())

    def _next_event(self, t: datetime) -> tuple[datetime, str] | None:
        s = self.v3_switches
        if (close := self._session_close_at()) is not None:
            return close, "session_close"   # a conversation is open: nothing else runs until it ends
        events = []
        m = rhythm.mode(t, self.v3, False)
        if s.stream or s.wakes:  # with the stream off, the monitor still checks at the stream's rhythm
            events.append((t + rhythm.stream_period(m, self.v3), "stream"))
        if s.sleep:
            events.append((rhythm.next_sleep(t, self.v3), "sleep"))
        return min(events) if events else None

    def advance(self, to: datetime) -> list[dict]:
        """Live through silence up to `to`. Returns the messages the agent wrote first, in order."""
        self.worker.drain()
        if not self.v3_switches.lives_in_silence:
            return []
        written: list[dict] = []
        t = self._cursor()
        for _ in range(MAX_EVENTS):
            nxt = self._next_event(t)
            if nxt is None or nxt[0] > to:
                break
            at, kind = nxt
            self._set_time(at)
            self._run_event(kind, at, written)
            t = at
            set_meta(self.db, CURSOR, iso(t))
        else:
            raise RuntimeError("advance(): the schedule did not reach `to`")
        set_meta(self.db, CURSOR, iso(max(t, min(to, self.clock.now()))))
        return written

    def _log_event(self, at: datetime, event: str, ran: bool, note: str = "") -> None:
        self.db.execute("INSERT INTO schedule_log(at, event, ran, note) VALUES (?, ?, ?, ?)",
                        (iso(at), event, int(ran), note))

    def _run_event(self, kind: str, at: datetime, written: list[dict]) -> None:
        if kind == "session_close":
            self.end_session()
            self._log_event(at, kind, True)
            if self.v3_switches.wakes:  # a conversation has just ended: the moment it is most likely to be thought over
                self._maybe_wake(at, rhythm.mode(at, self.v3, False), written)
        elif kind == "stream":
            self._stream_tick(at, written)
        elif kind == "sleep":
            if self._something_new_since_sleep(at):
                self._sleep(at)
                self._log_event(at, kind, True)
            else:
                self._log_event(at, kind, False, "nothing new since the last sleep")
            set_meta(self.db, LAST_SLEEP, iso(at))

    # ---------- mechanisms (filled in by later milestones) ----------

    def _stream_tick(self, at: datetime, written: list[dict]) -> None:
        m = rhythm.mode(at, self.v3, self.session is not None)
        if self.v3_switches.stream:
            ran = self.stream.tick(m) is not None
            self._log_event(at, "stream", ran, m if ran else f"{m}: no thought")
        if self.v3_switches.wakes:
            self._maybe_wake(at, m, written)

    def _due_acted(self, at: datetime) -> set[int]:
        stored = json.loads(get_meta(self.db, DUE_ACTED) or "{}")
        return set(stored.get("ids", [])) if stored.get("day") == at.date().isoformat() else set()

    def _maybe_wake(self, at: datetime, m: str, written: list[dict]) -> None:
        acted = self._due_acted(at)
        p = self.monitor.measure(at, get_meta(self.db, LAST_WAKE) or "0000", acted)
        why_not = None if p.ready else "below threshold"
        if why_not is None and m == rhythm.ASLEEP:
            why_not = "asleep"
        if why_not is None:
            why_not = self.monitor.capped(at, self.v3.wakes_per_day)
        self.monitor.log(at, p, why_not is None)
        if why_not is not None:
            return
        _, msgs = self.waker.wake(p)
        written.extend(msgs)
        set_meta(self.db, LAST_WAKE, iso(at))
        set_meta(self.db, DUE_ACTED, json.dumps({"day": at.date().isoformat(), "ids": sorted(acted | set(p.due))}))
        self._log_event(at, "wake", True, json.dumps(p.parts))

    def _sleep(self, at: datetime) -> None:
        pass
