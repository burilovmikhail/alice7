"""The self-narrative as a hypothesis (spec §6.9, T79–T84; decision D2).

V2's self-review contract still writes the portrait, beliefs and opinions, now once per sleep (not per session), from
the day's memories, thoughts and traces. It is shown under "What you believe about yourself — your own guess; it may
be wrong" and writes nothing into the field (§4.3).

Dissonance: in sleep, for each belief added or changed since the last check, the 6 traces most similar to it are
shown to the cheap model, which labels each supports / contradicts / unrelated (classification of concrete
episodes, not a narrative). dissonance = Σ belief weight × share contradicting feeds the drive. When it takes part
in a firing, the wake sees the belief next to the contradicting episodes. The narrative can change at the next
sleep; the traces don't.
"""

import json
import logging
from datetime import datetime

import numpy as np

from ..common.clock import iso
from ..common.db import get_meta, set_meta
from ..common.llm import as_int, as_list
from ..common.text import today_human
from ..v1.session import Session
from ..v2.context import Section
from ..v2.reflector import last_call_id
from ..v2.selfmodel import FIRST_TIME, NOT_FIRST, SELF_REVIEW_PROMPT, SelfModelMechanism
from . import constants as K
from .traces import KIND_WORDS, render

log = logging.getLogger(__name__)

GUESS_TITLE = "## What you believe about yourself — your own guess; it may be wrong"
GUESS_FRAMING = ("You wrote this about yourself after earlier days. It is a hypothesis, not a rule: what actually "
                 "happened counts for more than what you think of yourself.")
CHECKED_KEY = "v4_beliefs_checked"   # meta: [[text, weight], ...] of beliefs already checked against traces
LESSONS_LINE = ("- Your lessons about how to talk with the user are kept separately; don't list them, but your "
                "character should fit them.\n")

DISSONANCE_PROMPT = """You compare what someone believes about themselves with what actually happened. For each belief
below you get a few concrete episodes: what Alice was asked, how she answered, and how the user took it. Label each
episode for that belief: supports (the episode shows the belief holds), contradicts (it shows the belief doesn't
hold), or unrelated. Judge what happened in the episode, not what anyone said about it.

Reply with a JSON object:
{"beliefs": [{"belief": int, "labels": [{"episode": int, "label": "supports|contradicts|unrelated"}]}]}"""


class NarrativeMechanism(SelfModelMechanism):
    """The portrait shown as a guess; opinions as before; no self-review at the end of each session."""

    def system_section(self) -> Section | None:
        portrait = self.selfmodel.current()
        if portrait is None:
            return None
        return Section(GUESS_TITLE, portrait.content, GUESS_FRAMING, {"portrait_id": portrait.id})

    def after_session(self, session_id: int) -> None:
        return None   # the narrative is written once per sleep


class Narrator:
    def __init__(self, agent, model: str, check_model: str):
        self.agent, self.model, self.check_model = agent, model, check_model
        self.db, self.llm = agent.db, agent.llm

    # ---------- the review, once per sleep ----------

    def review(self, at: datetime, since: str) -> bool:
        a = self.agent
        sm = a.selfmodel
        previous = sm.current()
        episodes = self.db.execute("SELECT content FROM memories WHERE kind='episode' AND created_at > ? ORDER BY id",
                                   (since,)).fetchall()
        thoughts = self.db.execute("SELECT content, source FROM thoughts WHERE at > ? ORDER BY id", (since,)).fetchall()
        traces = self.db.execute("SELECT * FROM v4_traces WHERE created_at > ? ORDER BY id", (since,)).fetchall()
        if not episodes and not thoughts and not traces:
            return False
        name = a.store.user_name() or "The user"
        parts = []
        if previous:
            beliefs = "\n".join(f"[{b['id']}] ({b['weight']:.1f}) {b['text']}" for b in sm.beliefs(previous.id))
            parts.append(f"Your current portrait:\n{previous.content}\n\nYour current beliefs:\n{beliefs or '(none)'}")
        opinions = "\n".join(f"[{o['id']}] {o['topic']}: {o['content']}" for o in sm.opinions())
        parts.append(f"Your current opinions:\n{opinions or '(none)'}")
        if episodes:
            parts.append("Today's conversations:\n" + "\n".join(f"- {e['content']}" for e in episodes))
        if traces:
            parts.append("How your replies were taken today:\n" + "\n".join("- " + render(t, name) for t in traces))
        if thoughts:
            parts.append("What you thought on your own today (and dreamt):\n" + "\n".join(
                f"- {'(dream) ' if t['source'] == 'dream' else ''}{t['content']}" for t in thoughts))
        prompt = SELF_REVIEW_PROMPT.format(today=today_human(at.date()), first_time=FIRST_TIME if previous is None
                                           else NOT_FIRST, words=a.v2.portrait_words, intentions_part="",
                                           intentions_contract="")
        prompt = prompt.replace("A conversation with the user has\njust ended", "The day is over").replace(
            LESSONS_LINE, "")
        try:
            data = self.llm.json(prompt, "\n\n".join(parts), purpose="narrative", model=self.model)
        except Exception as e:
            log.warning("narrative review failed: %s", e)
            return False
        call_id = last_call_id(self.db, "narrative")
        portrait = data.get("portrait")
        beliefs = as_list(data.get("beliefs"), dict)
        changed = isinstance(portrait, str) and bool(portrait.strip()) and (
            previous is None or portrait.strip() != previous.content
            or a._mechanisms["selfmodel"].review._beliefs_changed(previous, beliefs))
        if changed:
            sm.save_portrait(portrait, changes=str(data.get("changes") or ""), beliefs=beliefs, llm_call_id=call_id)
        for o in as_list(data.get("opinions"), dict):
            sm.add_opinion(str(o.get("topic") or ""), str(o.get("content") or ""), o.get("stance"),
                           replaces=o.get("replaces"))
        return changed

    # ---------- dissonance ----------

    def check(self, at: datetime) -> float:
        """Label the traces nearest to each new or changed belief; returns the summed dissonance (0..1)."""
        a = self.agent
        portrait = a.selfmodel.current()
        if portrait is None:
            return 0.0
        beliefs = a.selfmodel.beliefs(portrait.id)
        checked = {tuple(x) for x in json.loads(get_meta(self.db, CHECKED_KEY) or "[]")}
        key = lambda b: (b["text"].strip().casefold(), round(float(b["weight"]), 2))
        todo = [b for b in beliefs if key(b) not in checked]
        traces = self.db.execute("SELECT * FROM v4_traces WHERE embedding IS NOT NULL ORDER BY id").fetchall()
        if todo and traces and a.store.embed is not None:
            self._label(at, todo, traces)
        set_meta(self.db, CHECKED_KEY, json.dumps(sorted({key(b) for b in beliefs} | checked)))
        return self.total(beliefs)

    def _label(self, at: datetime, todo: list, traces: list) -> None:
        a = self.agent
        mat = np.stack([np.frombuffer(t["embedding"], dtype=np.float32) for t in traces])
        try:
            vecs = a.store.embed([b["text"] for b in todo])
        except Exception as e:
            log.warning("dissonance embeddings failed: %s", e)
            return
        name = a.store.user_name() or "The user"
        shown, blocks = {}, []
        for n, (b, v) in enumerate(zip(todo, vecs)):
            near = [traces[int(k)] for k in np.argsort(-(mat @ v))[:K.DISSONANCE_TRACES]]
            shown[n] = near
            blocks.append(f"Belief {n}: {b['text']}\n" + "\n".join(f"  Episode {e}: " + render(t, name).replace("\n", " ")
                                                                    for e, t in enumerate(near)))
        try:
            data = self.llm.json(DISSONANCE_PROMPT, "\n\n".join(blocks), purpose="dissonance", model=self.check_model)
        except Exception as e:
            log.warning("dissonance check failed: %s", e)
            return
        labels: dict[int, dict[int, str]] = {}
        for item in as_list(data.get("beliefs"), dict):
            if (n := as_int(item.get("belief"))) in shown:
                labels[n] = {e: str(x.get("label")) for x in as_list(item.get("labels"), dict)
                             if (e := as_int(x.get("episode"))) is not None and e < len(shown[n])}
        for n, b in enumerate(todo):
            got = labels.get(n, {})
            sup = sum(1 for v in got.values() if v == "supports")
            con = sum(1 for v in got.values() if v == "contradicts")
            share = con / (sup + con) if sup + con else 0.0
            self.db.execute("INSERT INTO v4_dissonance(at, belief_id, belief, weight, trace_ids, labels, share, value) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (iso(at), b["id"], b["text"], b["weight"], json.dumps([t["id"] for t in shown[n]]),
                             json.dumps([got.get(e, "unrelated") for e in range(len(shown[n]))]), round(share, 4),
                             round(float(b["weight"]) * share, 4)))

    def _latest(self, beliefs: list) -> list:
        """The last check of each current belief (by wording)."""
        out = []
        for b in beliefs:
            row = self.db.execute("SELECT * FROM v4_dissonance WHERE lower(trim(belief))=? ORDER BY id DESC LIMIT 1",
                                  (b["text"].strip().casefold(),)).fetchone()
            if row is not None:
                out.append(row)
        return out

    def total(self, beliefs: list) -> float:
        return float(min(1.0, sum(r["value"] for r in self._latest(beliefs))))

    def block(self) -> str | None:
        """For a wake with dissonance in it: the most contradicted belief, next to what happened."""
        a = self.agent
        portrait = a.selfmodel.current()
        if portrait is None:
            return None
        rows = [r for r in self._latest(a.selfmodel.beliefs(portrait.id)) if r["share"] > 0]
        if not rows:
            return None
        top = max(rows, key=lambda r: r["value"])
        ids = [i for i, label in zip(json.loads(top["trace_ids"]), json.loads(top["labels"])) if label == "contradicts"]
        traces = a.traces.get(ids)
        if not traces:
            return None
        name = a.store.user_name() or "The user"
        return (f"You think of yourself like this: “{top['belief']}”. Here is what happened:\n"
                + "\n".join("- " + render(t, name) for t in traces))


__all__ = ["NarrativeMechanism", "Narrator", "KIND_WORDS"]
