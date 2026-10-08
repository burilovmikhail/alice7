"""B3 — reflective carry-over: B2's session-end notes plus what worked and what didn't in how the assistant talks
with this user (spec D9). The one-prompt version of what V2 does with an observer, lessons and a self-model:
if V2 doesn't beat it, V2's machinery isn't justified.

A V2-era reference condition, so it sits outside the V1 guard. It writes its notes with the same model V2
reflects with, so V2 vs. B3 compares mechanisms, not models. B2 itself is unchanged (fast model).
"""

import json
import logging

from ..common.db import set_meta
from ..v2.config import load_v2_config
from .agents import SummaryCarryOverAgent

log = logging.getLogger(__name__)

B3_PROMPT = """You maintain condensed notes that let an assistant continue a relationship with a user across
conversations. You get the current notes and the transcript of the conversation that just ended. Return updated
notes as JSON: keep everything still true and worth knowing (facts about the user and people in their life,
preferences, plans, agreements, what was discussed and when), update what changed, drop what is obsolete.
Use absolute dates. Write in the language of the conversation.

Also keep "how_i_talk": what in the assistant's manner worked or didn't with this user, judging by how the user
reacted, and what the assistant will do differently. Short first-person instructions ("I answer in connected prose,
without lists"). Keep what still holds; revise what the user's reactions contradict.

Reply with a JSON object:
{"facts": [str], "conversations": [{"date": "YYYY-MM-DD", "summary": str}], "how_i_talk": [str]}"""


class ReflectiveCarryOverAgent(SummaryCarryOverAgent):
    """B3: B2 + notes on how the assistant talks, written by the model V2 reflects with."""
    name = "B3"

    def __init__(self, cfg, clock, db_path=None, **kwargs):
        self.notes_model = load_v2_config().models(cfg)["reflect"]
        super().__init__(cfg, clock, db_path, **kwargs)

    def describe(self) -> dict:
        return {"notes_model": self.notes_model}

    def on_session_end(self, session_id: int) -> None:
        rows = self._messages("WHERE session_id=?", (session_id,))
        transcript = "\n".join(f"{'User' if r['role'] == 'user' else 'Alice'}: {r['content']}" for r in rows)
        started = self.db.execute("SELECT started_at FROM sessions WHERE id=?", (session_id,)).fetchone()[0]
        try:
            data = self.llm.json(B3_PROMPT,
                                 f"Current notes:\n{json.dumps(self.notes(), ensure_ascii=False) or '{}'}\n\n"
                                 f"Conversation on {started[:16]}:\n{transcript[-24000:]}",
                                 purpose="carryover", model=self.notes_model)
        except Exception as e:
            log.warning("carry-over failed: %s", e)
            return
        if data:
            set_meta(self.db, "carryover", json.dumps(data, ensure_ascii=False))
