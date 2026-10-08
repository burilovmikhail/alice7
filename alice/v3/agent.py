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
from ..v2.agent import AgentV2
from ..v2.switches import NAMES as V2_NAMES
from . import rhythm
from .config import V3Config, load_v3_config
from .schema import ensure_schema
from .switches import NAMES as V3_NAMES
from .switches import V3Switches

log = logging.getLogger(__name__)

CURSOR = "v3_cursor"          # meta: the sim time silence has been lived up to
LAST_SLEEP = "v3_last_sleep"  # meta: when the last nightly sleep ran
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
        self._v3_ready = True

    # ---------- switches ----------

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
        self._log_event(at, "stream", False, "not implemented yet")

    def _sleep(self, at: datetime) -> None:
        pass
