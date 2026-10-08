"""V2 agent: V1 plus procedural, prospective and self-knowledge memory (spec specs/v2/adaptive-identity.md).

AgentV2 subclasses the frozen AgentV1 and changes nothing in its memory: it swaps in a context builder that
adds V2 sections, records what V2 state each reply saw (turn_state), and hooks the per-turn and session-end
V2 steps. With every switch off it sends the chat model exactly what V1 sends."""

import json
import logging
from pathlib import Path

from ..common.clock import Clock
from ..common.config import Config
from ..common.db import get_meta, set_meta
from ..v1.agent import AgentV1
from ..v1.session import Session
from .chain import explain, summary
from .config import V2Config, load_v2_config
from .context import ContextV2
from .intentions import IntentionsMechanism, IntentionStore
from .lessons import LessonsMechanism, LessonStore
from .observer import Observer
from .reflector import Reflector
from .selfmodel import SelfModel, SelfModelMechanism, SelfReview
from .schema import ensure_schema
from .switches import NAMES, Switches

log = logging.getLogger(__name__)


class AgentV2(AgentV1):
    name = "V2"

    def __init__(self, cfg: Config, clock: Clock, db_path: Path | str | None = None, *, v2: V2Config | None = None,
                 switches: Switches | None = None, **kwargs):
        """switches: explicit build-time switches. Otherwise the ones this database was created with (so a probe
        fork keeps its run's switches), otherwise V2Config's."""
        self._v2_ready = False
        super().__init__(cfg, clock, db_path, **kwargs)
        self.v2 = v2 or load_v2_config()
        ensure_schema(self.db)
        stored = get_meta(self.db, "v2_switches")
        if switches is None:
            switches = Switches(**json.loads(stored)) if stored else self.v2.switches
        if stored is None:
            set_meta(self.db, "v2_switches", json.dumps(switches.as_dict()))
        self.switches = switches
        self.models = self.v2.models(cfg)
        self.context = ContextV2(self.store, cfg, clock, self.context.persona, self.active_mechanisms)
        self.lessons = LessonStore(self.store)
        self.reflector = Reflector(self.lessons, self.llm, self.models["reflect"])
        self.intentions = IntentionStore(self.store)
        self.selfmodel = SelfModel(self.store)
        self.observer = Observer(self.lessons, self.intentions, self.llm, self.models["observe"])
        review = SelfReview(self.selfmodel, self.lessons, self.intentions, self.llm, self.models["reflect"],
                            self.v2.portrait_words)
        # name -> mechanism, in session-end order: reflection first, so self-review sees this session's lessons
        self._mechanisms: dict[str, object] = {
            "lessons": LessonsMechanism(self.lessons, self.reflector, self.v2.lessons_budget),
            "selfmodel": SelfModelMechanism(self.selfmodel, review, lambda: self.switches),
            "intentions": IntentionsMechanism(self.intentions),
        }
        self._v2_ready = True
        AgentV1._recover(self)  # deferred from AgentV1.__init__: session-end steps need V2 set up

    # ---------- switches ----------

    def active_mechanisms(self) -> list:
        return [m for name, m in self._mechanisms.items() if getattr(self.switches, name)]

    def apply_switches(self, changes: dict[str, bool]) -> None:
        """Probe-time ablation, for forks only: the state stays, the mechanism stops being used."""
        self.switches = self.switches.with_(changes)

    def inject(self, *, portrait: str | None = None, beliefs=(), opinions=()) -> None:
        """False self-belief (E13), for forks only."""
        self.selfmodel.inject(portrait=portrait, beliefs=beliefs, opinions=opinions)

    def describe(self) -> dict:
        """For the run manifest."""
        return {"v2": self.v2.public(self.cfg), "switches": self.switches.as_dict()}

    # ---------- hooks into V1 ----------

    def _recover(self) -> None:
        if self._v2_ready:
            super()._recover()

    def reply(self, text: str) -> str:
        self.context.begin_turn()
        answer = super().reply(text)
        reply_id = self.session.buffer[-1]["id"]
        shown = self.context.shown
        self.db.execute(
            "INSERT OR REPLACE INTO turn_state(message_id, portrait_id, lesson_ids, opinion_ids, intention_ids, "
            "switches) VALUES (?, ?, ?, ?, ?, ?)",
            (reply_id, shown.get("portrait_id"), json.dumps(shown.get("lesson_ids", [])),
             json.dumps(shown.get("opinion_ids", [])), json.dumps(shown.get("intention_ids", [])),
             json.dumps(self.switches.as_dict())))
        return answer

    def _after_turn(self, session: Session) -> None:
        super()._after_turn(session)  # V1: extraction, fold
        if self.switches.lessons or self.switches.intentions:
            self.observer.observe(session, lessons=self.switches.lessons, intentions=self.switches.intentions)
            if self.switches.lessons and len(self.lessons.unreflected()) >= self.v2.reflect_every:
                self.reflector.reflect(session_summary=session.summary)
        for name in NAMES:
            if getattr(self.switches, name) and (m := self._mechanisms.get(name)) and hasattr(m, "after_turn"):
                m.after_turn(session)

    def _finalize(self, session_id: int) -> None:
        super()._finalize(session_id)
        for name in NAMES:
            if getattr(self.switches, name) and (m := self._mechanisms.get(name)) and hasattr(m, "after_session"):
                m.after_session(session_id)

    def last_reply_id(self) -> int | None:
        row = self.db.execute("SELECT MAX(message_id) FROM turn_state").fetchone()
        return row[0] if row else None

    def explain(self, message_id: int | None = None) -> dict:
        """The causal chain behind a reply (default: the last one)."""
        return explain(self.db, message_id or self.last_reply_id())

    def state_summary(self) -> dict:
        return summary(self.db)

    def last_state(self) -> dict:
        """V2 state shown for the last reply (empty dict for nothing)."""
        return dict(self.context.shown)
