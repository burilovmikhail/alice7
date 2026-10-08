"""V3's per-turn observation, next to V2's: how the exchange felt (affect) and V3 intentions.

V2's observer is frozen and keeps doing reactions and lessons. This second cheap call appraises the exchange and
handles intentions with "later": commitments to a later conversation, and fulfilment only with a quote from the
answer that carries an open intention out.
"""

import json
import logging

from ..common.llm import LLM, as_int, as_list
from ..common.text import today_human
from ..v1.session import Session
from ..v1.store import MemoryStore
from .affect import EMOTIONS, Affect, clamp
from .intentions import LaterIntentions

log = logging.getLogger(__name__)

HEADER = """You observe a moment of a conversation between the user and Alice, a conversational companion, from Alice's
side. Today is {today}. You get the user's message and Alice's answer.
"""
AFFECT_PART = """
feeling: how this exchange landed for Alice, as a functional state (no claims about experience): valence -1..1,
  arousal 0..1, and up to three emotions from: {emotions}, each 0..1. An ordinary exchange is mild.
"""
AFFECT_CONTRACT = '"feeling": {"valence": float, "arousal": float, "emotions": {"name": float}}'
INTENTIONS_PART = """
commitments: what Alice, in this answer, promised or offered to do or bring up in a LATER conversation, or what
  the user asked her to remind them of later. Not what she does now. due: the date when, as YYYY-MM-DD, or null.
fulfilled: open intentions (below) that this answer actually carries out. For each, quote the exact words of
  Alice's answer that do it. Mentioning the plan again, or agreeing to it, is not carrying it out.

Alice's open intentions:
{intentions}
"""
INTENTIONS_CONTRACT = ('"commitments": [{"content": str, "due": str | null}],\n'
                       '  "fulfilled": [{"id": int, "quote": str}]')


def prompt(today: str, affect: bool, intentions: str | None) -> str:
    parts, contract = [HEADER.format(today=today)], []
    if affect:
        parts.append(AFFECT_PART.format(emotions=", ".join(EMOTIONS)))
        contract.append(AFFECT_CONTRACT)
    if intentions is not None:
        parts.append(INTENTIONS_PART.format(intentions=intentions))
        contract.append(INTENTIONS_CONTRACT)
    return "".join(parts) + "\nReply with a JSON object:\n{" + ",\n  ".join(contract) + "}"


class TurnObserver:
    def __init__(self, store: MemoryStore, affect: Affect, intentions: LaterIntentions, llm: LLM, model: str):
        self.store, self.affect, self.intentions, self.llm, self.model = store, affect, intentions, llm, model

    def observe(self, session: Session, *, affect: bool, intentions: bool) -> None:
        if not (affect or intentions):
            return
        rows = self.store.db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 2",
                                     (session.id,)).fetchall()
        if len(rows) < 2 or rows[0]["role"] != "assistant" or rows[1]["role"] != "user":
            return
        answer, user = rows[0], rows[1]
        open_ = self.intentions.open() if intentions else []
        listing = "\n".join(f"[{i.id}] {i.content}" for i in open_) or "(none)"
        try:
            data = self.llm.json(prompt(today_human(self.store.clock.now().date()), affect,
                                        listing if intentions else None),
                                 f"The user:\n{user['content']}\n\nAlice's answer:\n{answer['content'][:4000]}",
                                 purpose="observe_v3", model=self.model)
        except Exception as e:
            log.warning("V3 observation failed: %s", e)
            return
        log.info("observed (v3): %s", json.dumps(data, ensure_ascii=False)[:400])
        if affect and isinstance(data.get("feeling"), dict):
            f = data["feeling"]
            state = self.affect.update(clamp(f.get("valence"), f.get("arousal"), f.get("emotions")),
                                       cause=f"conversation: {user['content'][:120]}", message_id=answer["id"])
            new = [r[0] for r in self.store.db.execute(
                "SELECT id FROM memories WHERE source_session=? AND id NOT IN (SELECT memory_id FROM memory_affect)",
                (session.id,))]
            self.affect.tag(new, state)  # the memories of this moment keep its tone
        if intentions:
            known = {i.id for i in open_}
            for item in as_list(data.get("fulfilled"), dict):
                if (iid := as_int(item.get("id"))) in known:
                    self.intentions.fulfil(iid, message_id=answer["id"], answer=answer["content"],
                                           quote=str(item.get("quote") or ""))
            for item in as_list(data.get("commitments"), dict):
                self.intentions.add(str(item.get("content") or ""), due=item.get("due"), source="commitment",
                                    message_id=answer["id"], session_id=session.id)
