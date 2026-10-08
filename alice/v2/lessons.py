"""Procedural memory: lessons — instructions to act, with a confidence that experience moves (spec §6.2).

A single case stays a hypothesis; repetition makes it a habit, which is always in the system prompt; contradiction
weakens it until it retires. Situational lessons ("when the question is about code: …") are shown only when the
message looks like that situation. Every change is an event that records what caused it (feedback ids, the
triggering message, the model call), so a changed behavior can be traced back (E7).
"""

import json
import logging
from dataclasses import dataclass

import numpy as np

from ..common.clock import iso, wall_now
from ..common.text import estimate_tokens, stem, words
from ..v1.session import Session
from ..v1.store import MemoryStore
from .context import Section

log = logging.getLogger(__name__)

CATEGORIES = ("style", "behavior", "user_model", "self")

ACTIVE = 0.55            # habit threshold: the lesson enters the system prompt
SITUATIONAL_MIN = 0.45   # situational lessons may be shown from here
SITUATION_SIM = 0.50     # cosine of the message to a lesson's situation to count as "this situation"
SAME_LESSON_SIM = 0.88   # a new lesson this close to an active one reinforces it instead
RETIRE = 0.20            # below this a weakened lesson retires
DIRECT = 0.80            # explicit instruction or the agent's own decision about itself
HYPOTHESIS_MAX = 0.60    # the reflector can't add a habit outright: repetition makes habits
REINFORCE = 0.35
WEAKEN = 0.40
CEILING = 0.97
SITUATIONAL_TOP = 3

HABITS_TITLE = "## How you've learned to talk with this user"
HABITS_FRAMING = ("What you have learned from your earlier conversations with this user about how to talk and act "
                  "with them. It comes from how those conversations went.")
SITUATIONAL_TITLE = "## In situations like this"
SITUATIONAL_FRAMING = "What you have learned from earlier conversations about situations like this one."


@dataclass
class Lesson:
    id: int
    category: str
    rule: str
    situation: str
    confidence: float
    evidence: int
    status: str
    updated_at: str


def _lesson(row) -> Lesson:
    return Lesson(row["id"], row["category"], row["rule"], row["situation"], row["confidence"], row["evidence"],
                  row["status"], row["updated_at"])


def _vec(blob) -> np.ndarray | None:
    return np.frombuffer(blob, dtype=np.float32) if blob else None


def _stems(text: str) -> set[str]:
    return {stem(w) for w in words(text) if len(w) > 3}


class LessonStore:
    def __init__(self, store: MemoryStore):
        self.store, self.db = store, store.db

    # ---------- reading ----------

    def active(self, min_confidence: float = 0.0) -> list[Lesson]:
        rows = self.db.execute("SELECT * FROM lessons WHERE status='active' AND confidence >= ? "
                               "ORDER BY confidence DESC, id", (min_confidence,)).fetchall()
        return [_lesson(r) for r in rows]

    def get(self, lesson_id, *, active_only: bool = True) -> Lesson | None:
        if not isinstance(lesson_id, int):
            return None
        row = self.db.execute("SELECT * FROM lessons WHERE id=?" + (" AND status='active'" if active_only else ""),
                              (lesson_id,)).fetchone()
        return _lesson(row) if row else None

    def habits(self, budget_tokens: int) -> list[Lesson]:
        """Learned lessons without a situation, most confident first, within the token budget."""
        out, used = [], 0
        for lesson in self.active(ACTIVE):
            if lesson.situation:
                continue
            cost = estimate_tokens(lesson.rule) + 1
            if used + cost > budget_tokens:
                continue  # a shorter, less confident habit may still fit
            used += cost
            out.append(lesson)
        return out

    def situational(self, query: str, limit: int = SITUATIONAL_TOP) -> list[Lesson]:
        candidates = {r["id"]: r for r in self.db.execute(
            "SELECT * FROM lessons WHERE status='active' AND situation != '' AND confidence >= ?", (SITUATIONAL_MIN,))}
        if not candidates or not query.strip():
            return []
        qv = self.store.embed_one(query)
        scored = []
        for row in candidates.values():
            sv = _vec(row["situation_embedding"])
            if qv is not None and sv is not None:
                sim = float(sv @ qv)
                if sim >= SITUATION_SIM:
                    scored.append((sim * row["confidence"], row))
            elif overlap := len(_stems(query) & _stems(row["situation"])):  # no vectors: shared words
                scored.append((overlap * row["confidence"], row))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [_lesson(r) for _, r in scored[:limit]]

    def find_similar(self, rule: str, situation: str = "") -> Lesson | None:
        text = f"{situation} {rule}".strip()
        vec = self.store.embed_one(text)
        best, best_sim = None, SAME_LESSON_SIM
        for row in self.db.execute("SELECT * FROM lessons WHERE status='active'"):
            if vec is not None and (other := _vec(row["embedding"])) is not None:
                sim = float(other @ vec)
            else:
                sim = 1.0 if f"{row['situation']} {row['rule']}".strip().casefold() == text.casefold() else 0.0
            if sim >= best_sim:
                best, best_sim = _lesson(row), sim
        return best

    def history(self, lesson_id: int) -> list:
        return self.db.execute("SELECT * FROM lesson_events WHERE lesson_id=? ORDER BY id", (lesson_id,)).fetchall()

    # ---------- changing ----------

    def add(self, category: str, rule: str, situation: str = "", confidence: float = 0.4, *, note: str = "",
            feedback_ids=(), message_id: int | None = None, llm_call_id: int | None = None) -> int | None:
        """New lesson, or a reinforcement of the same lesson if one is already active."""
        rule, situation = (rule or "").strip(), (situation or "").strip()
        if not rule:
            return None
        category = category if category in CATEGORIES else "behavior"
        cause = dict(feedback_ids=feedback_ids, message_id=message_id, llm_call_id=llm_call_id)
        if same := self.find_similar(rule, situation):
            # An explicit instruction matching a weakened lesson must still take effect as one would on its own
            self.reinforce(same.id, note=f"repeated: {note or rule}", at_least=float(confidence), **cause)
            return same.id
        confidence = max(0.05, min(CEILING, float(confidence)))
        vec = self.store.embed_one(f"{situation} {rule}".strip())
        svec = self.store.embed_one(situation) if situation else None
        now = self.store.now()
        lesson_id = self.db.execute(
            "INSERT INTO lessons(category, rule, situation, confidence, embedding, situation_embedding, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (category, rule, situation, confidence, vec.tobytes() if vec is not None else None,
             svec.tobytes() if svec is not None else None, now, now)).lastrowid
        self._event(lesson_id, "add", confidence, note, **cause)
        return lesson_id

    def reinforce(self, lesson_id: int, *, note: str = "", at_least: float = 0.0, **cause) -> None:
        """Confirmation: confidence grows, ever more slowly toward the ceiling."""
        if lesson := self.get(lesson_id):
            c = min(CEILING, max(lesson.confidence + (1 - lesson.confidence) * REINFORCE, at_least))
            self._update(lesson_id, "confidence=?, evidence=evidence+1", (c,))
            self._event(lesson_id, "reinforce", c, note, **cause)

    def weaken(self, lesson_id: int, *, note: str = "", **cause) -> None:
        """Contradiction: confidence falls; a lesson that falls below RETIRE retires."""
        if lesson := self.get(lesson_id):
            c = lesson.confidence * (1 - WEAKEN)
            if c < RETIRE:
                self.retire(lesson_id, note=note, **cause)
                return
            self._update(lesson_id, "confidence=?", (c,))
            self._event(lesson_id, "weaken", c, note, **cause)

    def revise(self, lesson_id: int, rule: str, situation: str | None = None, *, note: str = "", **cause) -> None:
        """Same lesson, understood more precisely: new wording or condition, confidence kept."""
        lesson = self.get(lesson_id)
        if lesson is None or not (rule or "").strip():
            return
        situation = lesson.situation if situation is None else situation.strip()
        vec = self.store.embed_one(f"{situation} {rule}".strip())
        svec = self.store.embed_one(situation) if situation else None
        self._update(lesson_id, "rule=?, situation=?, embedding=?, situation_embedding=?, evidence=evidence+1",
                     (rule.strip(), situation, vec.tobytes() if vec is not None else None,
                      svec.tobytes() if svec is not None else None))
        self._event(lesson_id, "revise", lesson.confidence, f"was: {lesson.rule}. {note}".strip(), **cause)

    def retire(self, lesson_id: int, *, note: str = "", **cause) -> None:
        if lesson := self.get(lesson_id):
            self._update(lesson_id, "status='retired'", ())
            self._event(lesson_id, "retire", lesson.confidence, note, **cause)

    def _update(self, lesson_id: int, set_sql: str, params: tuple) -> None:
        self.db.execute(f"UPDATE lessons SET {set_sql}, updated_at=? WHERE id=?", (*params, self.store.now(), lesson_id))

    def _event(self, lesson_id: int, op: str, confidence: float, note: str, *, feedback_ids=(),
               message_id: int | None = None, llm_call_id: int | None = None) -> None:
        log.info("lesson #%s %s -> %.2f: %s", lesson_id, op, confidence, note)
        self.db.execute(
            "INSERT INTO lesson_events(lesson_id, op, confidence, note, feedback_ids, message_id, llm_call_id, ts, "
            "sim_ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lesson_id, op, confidence, note, json.dumps(sorted(set(feedback_ids))), message_id, llm_call_id,
             wall_now().isoformat(timespec="milliseconds"), iso(self.store.clock.now())))

    # ---------- feedback ----------

    def add_feedback(self, *, session_id: int, assistant_msg_id: int, user_msg_id: int, signal: float, kind: str,
                     what: str, hint: str, llm_call_id: int | None) -> int:
        return self.db.execute(
            "INSERT INTO feedback(session_id, assistant_msg_id, user_msg_id, signal, kind, what, hint, llm_call_id, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, assistant_msg_id, user_msg_id, max(-1.0, min(1.0, float(signal))), kind or "neutral",
             what or "", hint or "", llm_call_id, self.store.now())).lastrowid

    def unreflected(self) -> list:
        return self.db.execute(
            """SELECT f.*, a.content AS assistant_text, u.content AS user_text
               FROM feedback f
               LEFT JOIN messages a ON a.id = f.assistant_msg_id
               LEFT JOIN messages u ON u.id = f.user_msg_id
               WHERE f.reflected = 0 ORDER BY f.id""").fetchall()

    def mark_reflected(self, feedback_ids) -> None:
        self.db.executemany("UPDATE feedback SET reflected=1 WHERE id=?", [(i,) for i in feedback_ids])


class LessonsMechanism:
    """The `lessons` switch: habits in the system prompt, situational lessons in <memory>, reflection."""

    def __init__(self, lessons: LessonStore, reflector, budget_tokens: int):
        self.lessons, self.reflector, self.budget = lessons, reflector, budget_tokens

    def system_section(self) -> Section | None:
        habits = self.lessons.habits(self.budget)
        if not habits:
            return None
        return Section(HABITS_TITLE, "\n".join(f"- {l.rule}" for l in habits), HABITS_FRAMING,
                       {"lesson_ids": [l.id for l in habits]})

    def memory_section(self, query: str, session: Session) -> Section | None:
        found = self.lessons.situational(query)
        if not found:
            return None
        return Section(SITUATIONAL_TITLE, "\n".join(f"- When {l.situation}: {l.rule}" for l in found),
                       SITUATIONAL_FRAMING, {"lesson_ids": [l.id for l in found]})

    def after_session(self, session_id: int) -> None:
        info = self.lessons.store.session_info(session_id)
        self.reflector.reflect(session_summary=(info["summary"] or "") if info else "")
