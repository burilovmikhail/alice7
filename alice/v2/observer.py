"""Self-observation after every turn (spec §6.3): how the user reacted to the previous reply, and what the agent
decided about itself. One fast-model call per user turn.

The observer reads the agent's replies as raw text and nothing computed from them, and its prompt names no
aspects of a reply to look at (spec D11): working out what a reaction was about is part of what is tested.
"""

import json
import logging

from ..common.llm import LLM, as_int, as_list
from ..common.text import today_human
from ..v1.session import Session
from .intentions import IntentionStore
from .lessons import DIRECT, LessonStore
from .reflector import format_lessons, last_call_id

log = logging.getLogger(__name__)

REPLY_CHARS = 4000
MIN_SIGNAL = 0.2   # weaker reactions are noise

HEADER = """You are the self-observation of Alice, a conversational companion. Today is {today}.
You get Alice's previous reply, the user's next message, and Alice's answer to it.
"""

LESSONS_PART = """
reaction: how the user reacted to Alice's PREVIOUS reply.
   signal: from -1 to 1. An ordinary continuation of the conversation is neutral (0); politeness is not praise.
   kind: correction (corrects Alice, "that's not it"), frustration (irritation, repeats the question, "you didn't
     get it"), praise (thanks, "great", "that's exactly it"), engagement (gets interested, develops the topic),
     disengagement (answers dryly, changes the topic, ignores a question), neutral.
   what: what in Alice's previous reply the reaction was about, in your own words.
   hint: how Alice should act in future, generalized; empty if it's too early to tell.
   explicit: true only if the user DIRECTLY said how Alice should behave ("be shorter", "don't call me that").
   category: style (how Alice talks) or behavior (what Alice does).
   If there is no previous reply, reaction is null.

self: decisions Alice made ABOUT HERSELF in her answer: how she will address the user, preferences and views
   she stated as her own, roles she took on. First person: "I call the user Theo, he left it to me." Simply using
   the user's name or answering the question is not a decision about herself. Facts about the user don't belong
   here. Usually empty.

replaces: ids of current lessons that a new explicit instruction or decision cancels.

Current lessons:
{lessons}
"""
LESSONS_CONTRACT = """"reaction": {"signal": float, "kind": str, "what": str, "hint": str, "explicit": bool,
               "category": "style|behavior"} | null,
  "self": [{"rule": str}],
  "replaces": [int]"""

INTENTIONS_PART = """
commitments: what Alice, in her answer, promised or said she would do or bring up in a LATER conversation
   ("next time I'll ask how the exam went"). Not what she does right away in the same answer. due: the date when,
   as YYYY-MM-DD, or null. Usually empty.

fulfilled: ids of Alice's open intentions that her answer carried out.

Alice's open intentions:
{intentions}
"""
INTENTIONS_CONTRACT = """"commitments": [{"content": str, "due": str | null}],
  "fulfilled": [int]"""


def observe_prompt(today: str, lessons: str | None, intentions: str | None) -> str:
    """Only the parts of the switched-on mechanisms; the contract is assembled to match."""
    parts, contract = [HEADER.format(today=today)], []
    if lessons is not None:
        parts.append(LESSONS_PART.format(lessons=lessons))
        contract.append(LESSONS_CONTRACT)
    if intentions is not None:
        parts.append(INTENTIONS_PART.format(intentions=intentions))
        contract.append(INTENTIONS_CONTRACT)
    return "".join(parts) + "\nReply with a JSON object:\n{" + ",\n  ".join(contract) + "}"


class Observer:
    def __init__(self, lessons: LessonStore, intentions: IntentionStore, llm: LLM, model: str):
        self.lessons, self.intentions, self.llm, self.model = lessons, intentions, llm, model
        self.db = lessons.db

    def _exchange(self, session: Session):
        """(previous reply in this session or None, the user's message, the agent's answer) for the last turn."""
        rows = self.db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 2",
                               (session.id,)).fetchall()
        if len(rows) < 2 or rows[0]["role"] != "assistant" or rows[1]["role"] != "user":
            return None
        answer, user = rows[0], rows[1]
        prev = self.db.execute("SELECT * FROM messages WHERE session_id=? AND role='assistant' AND id<? "
                               "ORDER BY id DESC LIMIT 1", (session.id, user["id"])).fetchone()
        return prev, user, answer

    def observe(self, session: Session, *, lessons: bool = True, intentions: bool = False) -> int | None:
        """Returns the id of the feedback row written, if any."""
        exchange = self._exchange(session)
        if exchange is None or not (lessons or intentions):
            return None
        prev, user, answer = exchange
        current = self.lessons.active() if lessons else []
        open_ = self.intentions.open() if intentions else []
        dialog = (f"Alice's previous reply:\n{prev['content'][:REPLY_CHARS]}\n\n" if prev
                  else "There is no previous reply (start of the conversation).\n\n")
        dialog += f"The user:\n{user['content']}\n\nAlice's answer:\n{answer['content'][:REPLY_CHARS]}"
        try:
            data = self.llm.json(
                observe_prompt(today_human(self.lessons.store.clock.now().date()),
                               format_lessons(current) if lessons else None,
                               ("\n".join(f"[{i.id}] {i.content}" for i in open_) or "(none)") if intentions else None),
                dialog, purpose="observe", model=self.model)
        except Exception as e:
            log.warning("self-observation failed: %s", e)
            return None
        log.info("observed: %s", json.dumps(data, ensure_ascii=False)[:500])
        call_id = last_call_id(self.db, "observe")
        if intentions:
            self._intentions(data, {i.id for i in open_}, answer["id"], session.id)
        if not lessons:
            return None
        known = {l.id for l in current}

        for old_id in map(as_int, as_list(data.get("replaces"))):
            if old_id in known:
                self.lessons.retire(old_id, note="cancelled by an explicit instruction or decision",
                                    message_id=user["id"], llm_call_id=call_id)
        for item in as_list(data.get("self"), dict):
            self.lessons.add("self", str(item.get("rule") or ""), confidence=DIRECT,
                             note="Alice's own decision in the conversation", message_id=answer["id"],
                             llm_call_id=call_id)

        r = data.get("reaction")
        if not isinstance(r, dict) or prev is None:
            return None
        try:
            signal = float(r.get("signal") or 0)
        except (TypeError, ValueError):
            signal = 0.0
        hint = str(r.get("hint") or "").strip()
        if r.get("explicit") is True and hint:
            # A direct instruction becomes a learned lesson at once, without waiting for statistics
            category = "style" if r.get("category") == "style" else "behavior"
            self.lessons.add(category, hint, confidence=DIRECT, note=f"explicit instruction: {user['content'][:200]}",
                             message_id=user["id"], llm_call_id=call_id)
            return None
        if abs(signal) < MIN_SIGNAL:
            return None
        return self.lessons.add_feedback(session_id=session.id, assistant_msg_id=prev["id"],
                                         user_msg_id=user["id"], signal=signal, kind=str(r.get("kind") or "neutral"),
                                         what=str(r.get("what") or ""), hint=hint, llm_call_id=call_id)

    def _intentions(self, data: dict, known: set[int], answer_id: int, session_id: int) -> None:
        for i in map(as_int, as_list(data.get("fulfilled"))):
            if i in known:
                self.intentions.close(i, "done", answer_id)
        for item in as_list(data.get("commitments"), dict):
            self.intentions.add(str(item.get("content") or ""), due=item.get("due"), source="commitment",
                                message_id=answer_id, session_id=session_id)
