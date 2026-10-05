"""V1 agent: one turn = retrieval -> context -> chat model -> persist -> extraction."""

import logging
import queue
import threading
from datetime import datetime
from pathlib import Path

from ..common.clock import Clock
from ..common.config import Config
from ..common.db import backup, connect
from ..common.llm import LLM, make_embedder
from ..common.prompts import load_persona
from ..common.trace import Tracer
from .context import ContextBuilder
from .extractor import Extractor
from .session import Session, finalize_session
from .store import Embedder, MemoryStore

log = logging.getLogger(__name__)

_DEFAULT = object()


class Worker:
    """Runs memory writes after the reply. Sync mode runs them inline (experiments: no timing effects).
    Background mode overlaps them with the user's typing; every public entry point drains the queue first,
    so the database is never touched from two threads at once."""

    def __init__(self, sync: bool):
        self.sync = sync
        self._q: queue.Queue | None = None
        if not sync:
            self._q = queue.Queue()
            threading.Thread(target=self._loop, name="v1-memory", daemon=True).start()

    def submit(self, fn) -> None:
        if self._q is None:
            self._run(fn)
        else:
            self._q.put(fn)

    def drain(self) -> None:
        if self._q is not None:
            self._q.join()

    def stop(self) -> None:
        if self._q is not None:
            self.drain()
            self._q.put(None)

    def _loop(self) -> None:
        while (fn := self._q.get()) is not None:
            try:
                self._run(fn)
            finally:
                self._q.task_done()
        self._q.task_done()

    @staticmethod
    def _run(fn) -> None:
        try:
            fn()
        except Exception:
            log.exception("memory write failed (messages stay unprocessed and are retried next turn)")


class AgentV1:
    name = "V1"

    def __init__(self, cfg: Config, clock: Clock, db_path: Path | str | None = None, *, llm: LLM | None = None,
                 embed: Embedder | None | object = _DEFAULT, sync_writes: bool | None = None,
                 persona: str | None = None, extract_after_reply: bool = True):
        """extract_after_reply=False is for probe forks: the probe turn itself is never scored for memory,
        so writing it would only cost money."""
        self.cfg, self.clock = cfg, clock
        self.db_path = Path(db_path or cfg.db_path)
        self.db = connect(self.db_path)
        self.tracer = Tracer(self.db, clock)
        self.llm = (llm or LLM(cfg)).bind(self.tracer)
        if embed is _DEFAULT:
            embed = make_embedder(cfg, self.llm)
        self.store = MemoryStore(self.db, clock, embed, self.tracer)
        self.extractor = Extractor(self.store, self.llm, clock)
        self.context = ContextBuilder(self.store, cfg, clock, persona or load_persona())
        sync = sync_writes if sync_writes is not None else bool(cfg.sync_writes)
        self.worker = Worker(sync)
        self.extract_after_reply = extract_after_reply
        self.session: Session | None = None
        self.last_memory_block: str | None = None
        self._last_context: list[int] = []
        try:
            self.store.backfill_embeddings()
        except Exception as e:
            log.warning("embedding backfill failed: %s", e)
        self._recover()

    @classmethod
    def load(cls, path: Path | str, cfg: Config, clock: Clock, **kwargs) -> "AgentV1":
        """Open an agent on an existing database (e.g. a probe fork made with snapshot())."""
        return cls(cfg, clock, path, **kwargs)

    # ---------- session lifecycle ----------

    def _gap_exceeded(self, session_id: int) -> bool:
        last = self.store.last_message(session_id)
        if not last:
            return False
        silence = (self.clock.now() - datetime.fromisoformat(last["ts"])).total_seconds() / 3600
        return silence >= self.cfg.session_gap_hours

    def _recover(self) -> None:
        """Sessions left open by a previous run: resume the latest if it's still fresh, finalize the rest."""
        open_ids = self.store.open_sessions()
        for sid in open_ids[:-1]:
            self._finalize(sid)
        if open_ids:
            sid = open_ids[-1]
            if self.store.message_count(sid) and not self._gap_exceeded(sid):
                self.session = Session.resume(self.store, self.llm, self.cfg, sid)
            else:
                self._finalize(sid)

    def _finalize(self, session_id: int) -> None:
        self.extractor.process_pending(session_id)  # flush extraction before the episode
        finalize_session(self.store, self.llm, self.clock, session_id)

    def _ensure_session(self) -> Session:
        if self.session is not None and self._gap_exceeded(self.session.id):
            log.info("session %s closed after silence", self.session.id)
            self.end_session()
        if self.session is None:
            self.session = Session.start(self.store, self.llm, self.cfg)
        return self.session

    def end_session(self) -> None:
        self.worker.drain()
        if self.session is not None:
            sid, self.session = self.session.id, None
            self._finalize(sid)

    # ---------- turn ----------

    def reply(self, text: str) -> str:
        self.worker.drain()
        session = self._ensure_session()
        block = self.context.memory_block(text, session)
        system = self.context.system_prompt()
        user_content = f"<memory>\n{block.text}\n</memory>\n\n{text}" if block.text else text
        messages = [{"role": "system", "content": system.text}, *session.history(),
                    {"role": "user", "content": user_content}]
        answer = self.llm.chat(messages, purpose="chat").strip()

        context_ids = system.core_ids + [i for i in block.shown_ids if i not in system.core_ids]
        user_id = session.add("user", text)  # persisted raw, without the <memory> block
        with self.tracer.cause(user_id):
            self.tracer.retrieval(message_id=user_id, query=text, hits=block.result.records(), purpose="chat")
            self.store.touch(block.shown_ids)
        session.add("assistant", answer, context_ids)
        self.last_memory_block = block.text
        self._last_context = context_ids
        if self.extract_after_reply:
            self.worker.submit(lambda: self._after_turn(session))
        return answer

    def _after_turn(self, session: Session) -> None:
        self.extractor.process_pending(session.id)
        session.maybe_fold()

    def last_context_ids(self) -> list[int]:
        return list(self._last_context)

    # ---------- inspection / harness ----------

    def drain(self) -> None:
        self.worker.drain()

    def snapshot(self, path: Path | str) -> None:
        """Consistent SQLite copy of the whole state (memory + trace). Used for probe forks."""
        self.worker.drain()
        backup(self.db, path)

    def cost(self) -> dict:
        self.worker.drain()
        return self.tracer.totals()

    def close(self) -> None:
        self.worker.stop()
        self.db.close()

