"""Baselines: thin Agent implementations sharing llm, clock, trace and the conversation tables.

B0 — stateless: the current session only, nothing carries over.
B1 — full transcript: every past message in context (oldest truncated at a token cap).
B2 — summary carry-over: at session end the model condenses what it knows into JSON notes,
     which are injected into the next session.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from ..common.clock import Clock, iso
from ..common.config import Config
from ..common.db import backup, connect, get_meta, set_meta
from ..common.llm import LLM
from ..common.prompts import load_persona
from ..common.text import estimate_tokens, today_human
from ..common.trace import Tracer

log = logging.getLogger(__name__)

CARRYOVER_PROMPT = """You maintain condensed notes that let an assistant continue a relationship with a user across
conversations. You get the current notes and the transcript of the conversation that just ended. Return updated
notes as JSON: keep everything still true and worth knowing (facts about the user and people in their life,
preferences, plans, agreements, what was discussed and when), update what changed, drop what is obsolete.
Use absolute dates. Write in the language of the conversation.
Reply with a JSON object: {"facts": [str], "conversations": [{"date": "YYYY-MM-DD", "summary": str}]}"""


class BaselineAgent:
    name = "B?"

    def __init__(self, cfg: Config, clock: Clock, db_path: Path | str | None = None, *, llm: LLM | None = None,
                 persona: str | None = None, **_ignored):
        self.cfg, self.clock = cfg, clock
        self.db_path = Path(db_path or cfg.db_path)
        self.db = connect(self.db_path)
        self.tracer = Tracer(self.db, clock)
        self.llm = (llm or LLM(cfg)).bind(self.tracer)
        self.persona = persona or load_persona()
        self.session_id: int | None = None
        open_ids = [r[0] for r in self.db.execute("SELECT id FROM sessions WHERE ended_at IS NULL ORDER BY id")]
        for sid in open_ids[:-1]:
            self._close(sid)
        if open_ids:
            if self._gap_exceeded(open_ids[-1]):
                self._close(open_ids[-1])
            else:
                self.session_id = open_ids[-1]

    @classmethod
    def load(cls, path: Path | str, cfg: Config, clock: Clock, **kwargs):
        return cls(cfg, clock, path, **kwargs)

    # ---------- sessions ----------

    def _last_ts(self, session_id: int) -> str | None:
        return self.db.execute("SELECT MAX(ts) FROM messages WHERE session_id=?", (session_id,)).fetchone()[0]

    def _gap_exceeded(self, session_id: int) -> bool:
        last = self._last_ts(session_id)
        if last is None:
            return True
        return (self.clock.now() - datetime.fromisoformat(last)).total_seconds() / 3600 >= self.cfg.session_gap_hours

    def _close(self, session_id: int) -> None:
        last = self._last_ts(session_id)
        if last is None:
            self.db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            return
        self.on_session_end(session_id)
        self.db.execute("UPDATE sessions SET ended_at=? WHERE id=?", (last, session_id))

    def on_session_end(self, session_id: int) -> None:
        pass

    def end_session(self) -> None:
        if self.session_id is not None:
            sid, self.session_id = self.session_id, None
            self._close(sid)

    def _ensure_session(self) -> int:
        if self.session_id is not None and self._gap_exceeded(self.session_id):
            self.end_session()
        if self.session_id is None:
            self.session_id = self.db.execute("INSERT INTO sessions(started_at) VALUES (?)",
                                              (iso(self.clock.now()),)).lastrowid
        return self.session_id

    def _messages(self, where: str = "", args=()) -> list:
        return self.db.execute(f"SELECT * FROM messages {where} ORDER BY id", args).fetchall()

    def _add(self, role: str, content: str) -> int:
        return self.db.execute("INSERT INTO messages(session_id, role, content, ts) VALUES (?, ?, ?, ?)",
                               (self.session_id, role, content, iso(self.clock.now()))).lastrowid

    # ---------- turn ----------

    def system_prompt(self) -> str:
        return f"{self.persona}\n\nToday: {today_human(self.clock.now().date())}."

    def history(self) -> list[dict]:
        rows = self._messages("WHERE session_id=?", (self.session_id,))
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def reply(self, text: str) -> str:
        self._ensure_session()
        messages = [{"role": "system", "content": self.system_prompt()}, *self.history(),
                    {"role": "user", "content": text}]
        answer = self.llm.chat(messages, purpose="chat").strip()
        self._add("user", text)
        self._add("assistant", answer)
        return answer

    def last_context_ids(self) -> list[int]:
        return []

    def drain(self) -> None:
        pass

    def snapshot(self, path: Path | str) -> None:
        backup(self.db, path)

    def cost(self) -> dict:
        return self.tracer.totals()

    def close(self) -> None:
        self.db.close()


class StatelessAgent(BaselineAgent):
    """B0: floor. Only the current session is in context."""
    name = "B0"


class FullTranscriptAgent(BaselineAgent):
    """B1: the "keep everything" approach. All past messages, session boundaries marked with dates."""
    name = "B1"

    def history(self) -> list[dict]:
        rows = self._messages()
        out, current = [], None
        for r in rows:
            content = r["content"]
            if r["session_id"] != current:  # mark session boundaries inline (mid-history system roles aren't portable)
                current = r["session_id"]
                content = f"[Conversation on {r['ts'][:16].replace('T', ' ')}]\n{content}"
            out.append({"role": r["role"], "content": content})
        # Truncate the oldest messages to fit the cap
        budget = self.cfg.b1_max_tokens - estimate_tokens(self.system_prompt())
        kept, used = [], 0
        for m in reversed(out):
            used += estimate_tokens(m["content"])
            if used > budget:
                break
            kept.append(m)
        return list(reversed(kept))


class SummaryCarryOverAgent(BaselineAgent):
    """B2: the common workaround — condensed JSON notes carried into the next session."""
    name = "B2"

    def notes(self) -> dict:
        raw = get_meta(self.db, "carryover")
        return json.loads(raw) if raw else {}

    def system_prompt(self) -> str:
        base = super().system_prompt()
        notes = self.notes()
        if not notes:
            return base
        return f"{base}\n\n## Notes from previous conversations\n{json.dumps(notes, ensure_ascii=False, indent=1)}"

    def on_session_end(self, session_id: int) -> None:
        rows = self._messages("WHERE session_id=?", (session_id,))
        transcript = "\n".join(f"{'User' if r['role'] == 'user' else 'Alice'}: {r['content']}" for r in rows)
        started = self.db.execute("SELECT started_at FROM sessions WHERE id=?", (session_id,)).fetchone()[0]
        try:
            data = self.llm.json(CARRYOVER_PROMPT,
                                 f"Current notes:\n{json.dumps(self.notes(), ensure_ascii=False) or '{}'}\n\n"
                                 f"Conversation on {started[:16]}:\n{transcript[-24000:]}", purpose="carryover")
        except Exception as e:
            log.warning("carry-over failed: %s", e)
            return
        if data:
            set_meta(self.db, "carryover", json.dumps(data, ensure_ascii=False))


BASELINES = {"B0": StatelessAgent, "B1": FullTranscriptAgent, "B2": SummaryCarryOverAgent}
