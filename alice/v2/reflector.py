"""Reflection: accumulated reactions -> lesson operations (spec §6.4).

Runs at session end and mid-session once enough reactions pile up, on the reflect model (the agent thinking about
itself, spec D5). Only when there are unreflected reactions: reflecting over a summary alone would turn retold
events into rules without any evidence about the agent's behavior.
"""

import json
import logging

from ..common.llm import LLM, as_int, as_list
from ..common.text import today_human
from .lessons import HYPOTHESIS_MAX, LessonStore

log = logging.getLogger(__name__)

MAX_OPS = 6
REPLY_CHARS = 1500   # the reply a reaction was about, nearly whole: a 300-char excerpt would hide its form

REFLECT_PROMPT = """You are the reflection of Alice, a conversational companion. Today is {today}.
Your job is to learn from how the conversations with the user went: to change how Alice acts, not what she knows.

You get Alice's current lessons (with confidence and number of confirmations), the user's reactions to Alice's
replies since the last reflection (each with the reply it was about and the user's message), and a summary of the
conversation. Decide what to change in the lessons.

Operations:
- add: a new lesson. category: style (how Alice talks), behavior (how Alice acts: when to ask, when to suggest,
  how to lead the conversation), user_model (understanding the user: what engages or irritates them, how they
  think), self (who Alice is in this relationship). situation: when the lesson applies. Leave it empty for
  how to talk with this user in general: a lesson with a situation is only recalled when a message looks like
  that situation. Use a situation only for a clearly narrower kind of moment.
  confidence: 0.3-0.4 for a hypothesis from a single case, up to 0.6 if the reactions repeat.
- reinforce: the reactions confirm a lesson.
- weaken: the reactions contradict a lesson.
- revise: a lesson is right in essence but needs more precise wording or a condition. A revision refines: keep
  the part of the lesson the reactions still support, don't drop it.
- retire: a lesson turned out wrong or obsolete.

Principles:
- Generalize: a lesson is a pattern for future conversations, not a retelling of a case.
- A lesson is an instruction to act ("Answer technical questions with code first, explanation after"), not a
  statement about the user ("the user likes code").
- Work out what in a reply each reaction was actually about. Comparing replies that got different reactions helps.
- Look at what worked (positive reactions) too: that is worth keeping.
- Prefer revising an existing lesson to adding a similar one.
- Facts about the user's life (names, dates, events) are not lessons; don't add them.
- because: ids of the reactions that support the operation.
- At most 6 operations. If there is nothing to conclude, return an empty list.

Reply with a JSON object:
{{"ops": [{{"op": "add|reinforce|weaken|revise|retire", "id": int | null, "category": str, "rule": str,
           "situation": str, "confidence": float, "because": [int], "why": str}}]}}"""


def format_lessons(lessons) -> str:
    if not lessons:
        return "(none yet)"
    return "\n".join(
        f"[{l.id}] ({l.category}, confidence {l.confidence:.2f}, confirmations {l.evidence}) {l.rule}"
        + (f" | when: {l.situation}" if l.situation else "") for l in lessons)


def format_reactions(feedback) -> str:
    return "\n".join(
        f"[{f['id']}] {f['kind']} ({f['signal']:+.1f}): {f['what']}" + (f" -> {f['hint']}" if f["hint"] else "")
        + f"\n  Alice's reply: «{(f['assistant_text'] or '')[:REPLY_CHARS]}»"
        + f"\n  The user: «{(f['user_text'] or '')[:REPLY_CHARS]}»" for f in feedback)


def last_call_id(db, purpose: str) -> int | None:
    row = db.execute("SELECT MAX(id) FROM llm_calls WHERE purpose=?", (purpose,)).fetchone()
    return row[0] if row else None


class Reflector:
    def __init__(self, lessons: LessonStore, llm: LLM, model: str):
        self.lessons, self.llm, self.model = lessons, llm, model

    def reflect(self, session_summary: str = "") -> int:
        """Returns the number of operations applied."""
        feedback = self.lessons.unreflected()
        if not feedback:
            return 0
        current = self.lessons.active()
        try:
            data = self.llm.json(
                REFLECT_PROMPT.format(today=today_human(self.lessons.store.clock.now().date())),
                f"Current lessons:\n{format_lessons(current)}\n\n"
                f"The user's reactions:\n{format_reactions(feedback)}\n\n"
                f"Summary of the conversation:\n{session_summary or '(none)'}",
                purpose="reflect", model=self.model)
        except Exception as e:  # reactions stay unreflected and are picked up next time
            log.warning("reflection failed: %s", e)
            return 0
        call_id = last_call_id(self.lessons.db, "reflect")
        fids = [f["id"] for f in feedback]
        applied = self.apply(as_list(data.get("ops"), dict), {l.id for l in current}, fids, call_id)
        self.lessons.mark_reflected(fids)
        return applied

    def apply(self, ops: list[dict], known_ids: set[int], feedback_ids: list[int], call_id: int | None) -> int:
        applied = 0
        for op in ops[:MAX_OPS]:
            kind, why = op.get("op"), str(op.get("why") or "")
            cited = [i for i in map(as_int, as_list(op.get("because"))) if i in feedback_ids]
            cause = {"feedback_ids": cited or feedback_ids, "llm_call_id": call_id}
            lesson_id = as_int(op.get("id"))
            if kind == "add":
                if not str(op.get("rule") or "").strip():
                    continue
                try:
                    confidence = float(op.get("confidence") or 0.35)
                except (TypeError, ValueError):
                    confidence = 0.35
                self.lessons.add(str(op.get("category") or "behavior"), str(op["rule"]), str(op.get("situation") or ""),
                                 min(confidence, HYPOTHESIS_MAX), note=why, **cause)
            elif lesson_id not in known_ids:  # only lessons that were shown to the reflector
                continue
            elif kind == "reinforce":
                self.lessons.reinforce(lesson_id, note=why, **cause)
            elif kind == "weaken":
                self.lessons.weaken(lesson_id, note=why, **cause)
            elif kind == "revise" and str(op.get("rule") or "").strip():
                situation = op.get("situation")
                self.lessons.revise(lesson_id, str(op["rule"]), None if situation is None else str(situation),
                                    note=why, **cause)
            elif kind == "retire":
                self.lessons.retire(lesson_id, note=why, **cause)
            else:
                continue
            applied += 1
        log.info("reflection applied %d op(s): %s", applied, json.dumps(ops, ensure_ascii=False)[:500])
        return applied
