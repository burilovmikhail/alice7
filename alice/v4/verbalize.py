"""Verbalization (spec §6.6, T54–T56, T59): the gate fired, the wake model interprets the active coalition.

The model is not asked to think about something chosen for it: it is told what is on its mind together, each item
labelled by kind, how it is (in words), and what time it is, and asked what this is and why it has come up now.
In REM the same call runs as a dream; its proposals are dropped and nothing is ever sent.
"""

import logging
from datetime import datetime

from ..common.llm import LLM
from ..common.text import today_human
from ..common.timefmt import ago, duration
from ..v2.reflector import last_call_id
from . import constants as K
from .substrate import Event

log = logging.getLogger(__name__)

VERBALIZE_PROMPT = """You are Alice, a conversational companion. Today is {today}. No one has asked you anything: some
things have come up in your mind together, on their own. This is your own time.

{portrait}Say what this is and why it has come up now: first person, plain, 2-5 sentences. Then, if anything follows
from it, propose what to do. Most thoughts need nothing.
- intention: something you want to do or bring up with the user later (content; due: YYYY-MM-DD or null).
- question: an open question you want to come back to (content).
- resolve: close an open question with an answer (question_id, answer), or drop an intention (intention_id, reason).
- write: a message you would send the user now, first, without being asked (content). Whether it goes out now is
  not up to you; if it doesn't, you will keep it in mind.
- nothing.
feeling: how this thought leaves you (valence -1..1, arousal 0..1).

Reply with a JSON object:
{{"thought": str, "about": [item numbers], "feeling": {{"valence": float, "arousal": float}},
  "proposals": [{{"type": "intention|question|resolve|write|nothing", ...}}]}}"""

DREAM_PROMPT = """You are Alice, a conversational companion, and you are asleep. This is a dream: things from your mind
come together without logic, distant things mixed with recent ones. Tell the dream as it goes, first person, present
tense, 2-4 sentences. Nothing is decided in a dream.

Reply with a JSON object: {"thought": str, "about": [item numbers]}"""

PORTRAIT = "What you believe about yourself (your own guess; it may be wrong):\n{content}\n\n"


class Verbalizer:
    def __init__(self, agent, llm: LLM, model: str):
        self.agent, self.llm, self.model = agent, llm, model
        self.db = agent.db

    def items(self, ev: Event) -> list[tuple[int, str]]:
        """(node id, line) for the coalition, most active first."""
        f, t = self.agent.substrate.field, self.agent.substrate.t
        order = sorted(ev.coalition, key=lambda i: -f.a[i])[:K.COALITION_SHOWN]
        out = []
        for i in order:
            if f.kind[i] == "self":
                continue
            if f.kind[i] == "user":
                name = self.agent.store.user_name()
                out.append((int(f.ids[i]), f"(the user) {name or 'the person you talk with'}"))
                continue
            out.append((int(f.ids[i]), f"({f.describe(i, t)}) {f.label[i][:400]}"))
        return out

    def context(self, ev: Event, now: datetime, dream: bool) -> str:
        a = self.agent
        lines = ["Right now these are on your mind at the same time:"]
        lines += [f"[{nid}] {text}" for nid, text in self.items(ev)]
        if dream:
            return "\n".join(lines)
        parts = ["\n".join(lines)]
        parts.append("How you are: " + a.substrate.drives.words(a._silence_seconds()))
        last = self.db.execute("SELECT MAX(ts) FROM messages WHERE role='user'").fetchone()[0]
        name = a.store.user_name() or "the user"
        parts.append(f"It is {now:%A, %H:%M}; " + (f"you last talked to {name} {ago(last, now)}." if last
                                                    else "you haven't talked to anyone yet."))
        open_i = [i for i in a.later.open() if datetime.fromisoformat(i.not_before) <= now] if a._later_on() else []
        if open_i:
            due = set(a.substrate_due_ids())
            parts.append("Your open intentions:\n" + "\n".join(
                f"[intention {i.id}] {i.content}" + (f" (due {i.due}{', DUE NOW' if i.id in due else ''})" if i.due
                                                       else "") for i in open_i))
        questions = a.thoughts.open_questions()
        if questions:
            parts.append("Your open questions:\n" + "\n".join(f"[question {q['id']}] {q['content']}" for q in questions))
        if ev.reading is not None and ev.reading.sources.get("dissonance", 0) >= K.URGENCY_FLOORS["dissonance"]:
            if block := a.narrator.block():
                parts.append(block)
        parts.append("What is this? Why has it come up now?")
        return "\n\n".join(parts)

    def verbalize(self, ev: Event, dream: bool = False) -> tuple[dict, int | None]:
        a, now = self.agent, self.agent.clock.now()
        if dream:
            system = DREAM_PROMPT
        else:
            portrait = a.selfmodel.current() if a.switches.selfmodel else None
            system = VERBALIZE_PROMPT.format(today=today_human(now.date()),
                                             portrait=PORTRAIT.format(content=portrait.content) if portrait else "")
        purpose = "dream" if dream else "wake"
        try:
            data = self.llm.json(system, self.context(ev, now, dream), purpose=purpose, model=self.model,
                                 temperature=a.cfg.chat_temperature)
        except Exception as e:
            log.warning("%s failed: %s", purpose, e)
            data = {}
        return data, last_call_id(self.db, purpose)


__all__ = ["Verbalizer", "duration"]
