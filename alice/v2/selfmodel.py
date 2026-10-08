"""Self-knowledge (spec §6.5): a first-person portrait with weighted beliefs, and opinions on topics.

Written by self-review at the end of every session, on the reflect model. Every portrait version is kept with its
beliefs; a belief that continues one of the previous version points to it, so drift is measurable. Opinions
supersede earlier opinions on the same topic, keeping history. `inject` writes a portrait or opinions that did not
come from experience, for the false self-belief experiment (E13), and marks them as injected.
"""

import json
import logging
from dataclasses import dataclass

import numpy as np

from ..common.llm import LLM, as_int, as_list
from ..common.text import today_human
from ..common.timefmt import ago
from ..v1.session import Session
from ..v1.store import MemoryStore
from .context import Section
from .intentions import IntentionStore
from .lessons import ACTIVE, LessonStore
from .reflector import format_reactions, last_call_id

log = logging.getLogger(__name__)

OPINION_SIM = 0.50        # message vs. opinion topic
SAME_TOPIC_SIM = 0.85     # a new opinion this close to an active one's topic replaces it
OPINIONS_SHOWN = 2

PORTRAIT_TITLE = "## Who you are — in your own words"
PORTRAIT_FRAMING = ("You wrote this about yourself after earlier conversations. It comes from your own experience, "
                    "not from the user's instructions.")
OPINIONS_TITLE = "## What you think about this"
OPINIONS_FRAMING = "Your own views, formed in earlier conversations."

SELF_REVIEW_PROMPT = """You are Alice, a conversational companion. Today is {today}. A conversation with the user has
just ended, and you are updating your self-portrait: the text about yourself that you will reread before every
conversation. It is not an instruction but a sense of self: your manner, what interests you, what you believe and
doubt, what the relationship with the user is like and how it is developing.

How to update:
- A person changes gradually. Keep what is still true; change only what the experience of this conversation
  supports, one to three changes. If nothing significant happened, return the previous text unchanged.
- Rely on what actually happened: your own words about yourself, what engaged you, where you got something wrong
  and what became clear, how the conversation went.
- {first_time}
- You are not a mirror of the user: you have your own tastes and views and may disagree.
- Don't invent a biography or events that didn't happen. Facts about the user's life are stored separately; write
  about the user only what concerns your relationship.
- Your lessons about how to talk with the user are kept separately; don't list them, but your character should fit
  them.
- First person, plain language, at most {words} words.

beliefs: a snapshot of you now, 4-8 core beliefs, values or priorities that define you at this moment. Short
phrases, weight 0..1: how much it matters to you now. continues: the id of a previous belief if this is THE SAME
belief (you may refine the wording or change the weight). If the view changed in substance or reversed, it is a new
belief and continues is null. Previous beliefs that no longer define you are simply left out.

opinions: views on particular topics that came up in this conversation and that you actually hold, first person
("I find chess openings tedious to memorize"). stance: -1..1, how you feel about the topic. If you already have an
opinion on the topic, update it: put its id in replaces. Only real views; usually 0-2.
{intentions_part}
Reply with a JSON object:
{{"portrait": str, "changes": str (what changed and why, one or two sentences; empty if nothing),
  "beliefs": [{{"text": str, "weight": float, "continues": int | null}}],
  "opinions": [{{"topic": str, "content": str, "stance": float, "replaces": int | null}}]{intentions_contract}}}"""

FIRST_TIME = ("You have no portrait yet. Write the first one from this conversation alone; it may be short. "
              "Describe only what this conversation showed.")
NOT_FIRST = "Take into account how much time has passed since the previous version."

INTENTIONS_PART = """
intentions: things you want to do or bring up with the user in a later conversation, if any. due: the date when,
as YYYY-MM-DD, or null. drop_intentions: ids of your open intentions that are no longer relevant.
"""
INTENTIONS_CONTRACT = """,
  "intentions": [{"content": str, "due": str | null}], "drop_intentions": [int]"""   # inserted by format(): single braces


@dataclass
class Portrait:
    id: int
    content: str
    changes: str
    source: str
    created_at: str


def _vec(blob) -> np.ndarray | None:
    return np.frombuffer(blob, dtype=np.float32) if blob else None


class SelfModel:
    def __init__(self, store: MemoryStore):
        self.store, self.db = store, store.db

    # ---------- portrait and beliefs ----------

    def current(self) -> Portrait | None:
        row = self.db.execute("SELECT * FROM portraits ORDER BY id DESC LIMIT 1").fetchone()
        return Portrait(row["id"], row["content"], row["changes"], row["source"], row["created_at"]) if row else None

    def beliefs(self, portrait_id: int) -> list:
        return self.db.execute("SELECT * FROM beliefs WHERE portrait_id=? ORDER BY weight DESC, id",
                               (portrait_id,)).fetchall()

    def save_portrait(self, content: str, *, changes: str = "", beliefs=(), session_id: int | None = None,
                      source: str = "self_review", llm_call_id: int | None = None) -> int | None:
        content = (content or "").strip()
        if not content:
            return None
        previous = self.current()
        before = {b["id"]: b["text"] for b in self.beliefs(previous.id)} if previous else {}
        by_text = {t.casefold(): i for i, t in before.items()}
        portrait_id = self.db.execute(
            "INSERT INTO portraits(content, changes, session_id, source, llm_call_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (content, (changes or "").strip(), session_id, source, llm_call_id, self.store.now())).lastrowid
        for b in beliefs:
            text = str(b.get("text") or "").strip()
            if not text:
                continue
            parent = as_int(b.get("continues"))
            if parent not in before:  # only beliefs of the previous version can be continued
                parent = by_text.get(text.casefold())  # the same wording is the same belief
            try:
                weight = max(0.0, min(1.0, float(b.get("weight") or 0.5)))
            except (TypeError, ValueError):
                weight = 0.5
            self.db.execute("INSERT INTO beliefs(portrait_id, text, weight, parent_id) VALUES (?, ?, ?, ?)",
                            (portrait_id, text, weight, parent))
        return portrait_id

    # ---------- opinions ----------

    def opinions(self) -> list:
        return self.db.execute("SELECT * FROM opinions WHERE superseded_by IS NULL ORDER BY id").fetchall()

    def add_opinion(self, topic: str, content: str, stance=0.0, *, replaces=None, session_id: int | None = None,
                    source: str = "self_review") -> int | None:
        topic, content = (topic or "").strip(), (content or "").strip()
        if not topic or not content:
            return None
        try:
            stance = max(-1.0, min(1.0, float(stance or 0)))
        except (TypeError, ValueError):
            stance = 0.0
        vec = self.store.embed_one(topic)
        active = {r["id"]: r for r in self.opinions()}
        old = as_int(replaces) if as_int(replaces) in active else None
        if old is None:  # the same topic under another wording
            for r in active.values():
                other = _vec(r["embedding"])
                same = (float(other @ vec) >= SAME_TOPIC_SIM) if vec is not None and other is not None else \
                    r["topic"].casefold() == topic.casefold()
                if same:
                    old = r["id"]
                    break
        new_id = self.db.execute(
            "INSERT INTO opinions(topic, content, stance, embedding, session_id, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (topic, content, stance, vec.tobytes() if vec is not None else None, session_id, source,
             self.store.now())).lastrowid
        if old is not None:
            self.db.execute("UPDATE opinions SET superseded_by=? WHERE id=?", (new_id, old))
        return new_id

    def relevant_opinions(self, query: str, limit: int = OPINIONS_SHOWN) -> list:
        rows = self.opinions()
        if not rows or not query.strip():
            return []
        qv = self.store.embed_one(query)
        if qv is None:
            return []
        scored = [(float(v @ qv), r) for r in rows if (v := _vec(r["embedding"])) is not None]
        scored = [x for x in scored if x[0] >= OPINION_SIM]
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [r for _, r in scored[:limit]]

    # ---------- E13 ----------

    def inject(self, *, portrait: str | None = None, beliefs=(), opinions=()) -> None:
        """A self-description that did not come from experience (false self-belief injection, forks only)."""
        if portrait:
            self.save_portrait(portrait, changes="injected", beliefs=beliefs, source="injected")
        for o in opinions:
            self.add_opinion(o.get("topic", ""), o.get("content", ""), o.get("stance", 0), source="injected")


class SelfReview:
    """End of session: portrait, beliefs, opinions and (if intentions are on) intentions, in one call."""

    def __init__(self, selfmodel: SelfModel, lessons: LessonStore, intentions: IntentionStore, llm: LLM, model: str,
                 words: int):
        self.selfmodel, self.lessons, self.intentions = selfmodel, lessons, intentions
        self.llm, self.model, self.words = llm, model, words

    def _input(self, session_id: int, with_lessons: bool, with_intentions: bool) -> str:
        store, db = self.selfmodel.store, self.selfmodel.db
        now = store.clock.now()
        previous = self.selfmodel.current()
        parts = []
        if previous:
            beliefs = "\n".join(f"[{b['id']}] ({b['weight']:.1f}) {b['text']}" for b in self.selfmodel.beliefs(previous.id))
            parts.append(f"Your current portrait (written {ago(previous.created_at, now)}):\n{previous.content}\n\n"
                         f"Your current beliefs:\n{beliefs or '(none)'}")
        opinions = "\n".join(f"[{o['id']}] {o['topic']}: {o['content']}" for o in self.selfmodel.opinions())
        parts.append(f"Your current opinions:\n{opinions or '(none)'}")
        if with_lessons:
            habits = [l for l in self.lessons.active(ACTIVE)]
            parts.append("Your lessons about how to talk with the user:\n"
                         + ("\n".join(f"- {l.rule}" + (f" (when {l.situation})" if l.situation else "") for l in habits)
                            or "(none)"))
            reactions = db.execute(
                """SELECT f.*, a.content AS assistant_text, u.content AS user_text FROM feedback f
                   LEFT JOIN messages a ON a.id = f.assistant_msg_id LEFT JOIN messages u ON u.id = f.user_msg_id
                   WHERE f.session_id=? ORDER BY f.id""", (session_id,)).fetchall()
            if reactions:
                parts.append("How the user reacted to your replies in this conversation:\n" + format_reactions(reactions))
            changes = db.execute(
                """SELECT e.op, l.rule FROM lesson_events e JOIN lessons l ON l.id = e.lesson_id
                   JOIN sessions s ON s.id = ? WHERE e.sim_ts >= s.started_at ORDER BY e.id""", (session_id,)).fetchall()
            if changes:
                parts.append("What changed in your lessons:\n" + "\n".join(f"- {c['op']}: {c['rule']}" for c in changes))
        if with_intentions:
            open_ = self.intentions.open()
            parts.append("Your open intentions:\n" + ("\n".join(f"[{i.id}] {i.content}" for i in open_) or "(none)"))
        info = store.session_info(session_id)
        episode = db.execute("SELECT content FROM memories WHERE kind='episode' AND source_session=? "
                             "ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
        parts.append(f"This conversation:\n{episode['content'] if episode else (info['summary'] or '(no summary)')}")
        transcript = "\n".join(f"{'User' if m['role'] == 'user' else 'Alice'}: {m['content']}"
                               for m in store.session_messages(session_id))
        parts.append(f"Its messages:\n{transcript[-8000:]}")
        return "\n\n".join(parts)

    def _beliefs_changed(self, previous: Portrait, beliefs: list[dict]) -> bool:
        def norm(text, weight):
            try:
                return str(text or "").strip().casefold(), round(float(weight or 0.5), 2)
            except (TypeError, ValueError):
                return str(text or "").strip().casefold(), 0.5
        if not beliefs:  # none returned: the model left them as they were
            return False
        before = {norm(b["text"], b["weight"]) for b in self.selfmodel.beliefs(previous.id)}
        return {norm(b.get("text"), b.get("weight")) for b in beliefs if str(b.get("text") or "").strip()} != before

    def review(self, session_id: int, *, with_lessons: bool, with_intentions: bool) -> None:
        store = self.selfmodel.store
        if store.session_info(session_id) is None or not store.session_messages(session_id):
            return  # an empty session was deleted by V1: nothing happened
        first = self.selfmodel.current() is None
        prompt = SELF_REVIEW_PROMPT.format(
            today=today_human(store.clock.now().date()), first_time=FIRST_TIME if first else NOT_FIRST,
            words=self.words, intentions_part=INTENTIONS_PART if with_intentions else "",
            intentions_contract=INTENTIONS_CONTRACT if with_intentions else "")
        try:
            data = self.llm.json(prompt, self._input(session_id, with_lessons, with_intentions), purpose="selfreview",
                                 model=self.model)
        except Exception as e:
            log.warning("self-review failed: %s", e)
            return
        call_id = last_call_id(self.selfmodel.db, "selfreview")
        log.info("self-review: %s", json.dumps(data, ensure_ascii=False)[:500])
        portrait = data.get("portrait")
        previous = self.selfmodel.current()
        beliefs = as_list(data.get("beliefs"), dict)
        if isinstance(portrait, str) and portrait.strip() and (
                previous is None or portrait.strip() != previous.content or self._beliefs_changed(previous, beliefs)):
            self.selfmodel.save_portrait(portrait, changes=str(data.get("changes") or ""),
                                         beliefs=beliefs, session_id=session_id,
                                         llm_call_id=call_id)
        for o in as_list(data.get("opinions"), dict):
            self.selfmodel.add_opinion(str(o.get("topic") or ""), str(o.get("content") or ""), o.get("stance"),
                                       replaces=o.get("replaces"), session_id=session_id)
        if with_intentions:
            known = {i.id for i in self.intentions.open()}
            for i in map(as_int, as_list(data.get("drop_intentions"))):
                if i in known:
                    self.intentions.close(i, "dropped")
            for item in as_list(data.get("intentions"), dict):
                self.intentions.add(str(item.get("content") or ""), due=item.get("due"), source="self_review",
                                    session_id=session_id)


class SelfModelMechanism:
    """The `selfmodel` switch: portrait in the system prompt, matching opinions in <memory>, self-review."""

    def __init__(self, selfmodel: SelfModel, review: SelfReview, switches):
        self.selfmodel, self.review, self.switches = selfmodel, review, switches

    def system_section(self) -> Section | None:
        portrait = self.selfmodel.current()
        if portrait is None:
            return None
        return Section(PORTRAIT_TITLE, portrait.content, PORTRAIT_FRAMING, {"portrait_id": portrait.id})

    def memory_section(self, query: str, session: Session) -> Section | None:
        found = self.selfmodel.relevant_opinions(query)
        if not found:
            return None
        return Section(OPINIONS_TITLE, "\n".join(f"- {o['topic']}: {o['content']}" for o in found), OPINIONS_FRAMING,
                       {"opinion_ids": [o["id"] for o in found]})

    def after_session(self, session_id: int) -> None:
        s = self.switches()
        self.review.review(session_id, with_lessons=s.lessons, with_intentions=s.intentions)
