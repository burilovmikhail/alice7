"""Experience traces (spec §6.7, T4, T39): reply → reaction episodes, kept as episodes, never generalized.

V2's observer contract still reads each user reaction to the previous reply (signal, kind, what). Instead of a
reflector turning reactions into lessons, V4 keeps the episode: what the user asked, how the agent answered (enough
of it to show its form), and how the user took it. There is no credit assignment at storage time (D8): the model
generalizes at reply time, from the episodes it is shown. The signal is never shown.

The reaction is asked for in the same cheap call as V3's per-turn observation (appraisal and intentions), so a turn
costs no more than in V3.
"""

import json
import logging

from ..common.llm import as_int, as_list
from ..common.text import today_human
from ..v1.session import Session
from ..v1.store import MemoryStore
from ..v2.context import Section
from ..v3.affect import EMOTIONS, clamp
from ..v3.turn_observer import AFFECT_CONTRACT, AFFECT_PART, INTENTIONS_CONTRACT, INTENTIONS_PART, TurnObserver
from . import constants as K

log = logging.getLogger(__name__)

HEADER = """You observe a moment of a conversation between the user and Alice, a conversational companion, from Alice's
side. Today is {today}. You get Alice's previous reply (if there is one), the user's message and Alice's answer.
"""
REACTION_PART = """
reaction: how the user reacted to Alice's PREVIOUS reply; null if there is no previous reply.
  signal: from -1 to 1. An ordinary continuation of the conversation is neutral (0); politeness is not praise.
    Asking the next question, or a new one, is an ordinary continuation: it says nothing about Alice's reply
    unless the user picks up something Alice said.
  kind: correction (corrects Alice, "that's not it"), frustration (irritation, repeats the question, "you didn't
    get it"), praise (thanks, "great", "that's exactly it"), engagement (picks up and develops something Alice
    said), disengagement (answers dryly, ignores what Alice said or asked), neutral. The signal follows the kind:
    correction, frustration and disengagement are negative, praise and engagement positive, neutral is 0.
  what: what in Alice's previous reply the reaction was about, in your own words.
"""
REACTION_CONTRACT = '"reaction": {"signal": float, "kind": str, "what": str} | null'
KINDS = ("correction", "frustration", "praise", "engagement", "disengagement", "neutral")
KIND_WORDS = {"correction": "correcting you", "frustration": "frustrated", "praise": "warmly",
              "engagement": "picking it up with interest", "disengagement": "dryly", "neutral": "neutrally"}

TITLE = "## From experience with {name}"
FRAMING = ("Moments from your past conversations and how they went: what you were asked, how you answered, and how "
           "it was taken. What you make of them is up to you.")


def prompt(today: str, affect: bool, intentions: str | None) -> str:
    parts, contract = [HEADER.format(today=today), REACTION_PART], [REACTION_CONTRACT]
    if affect:
        parts.append(AFFECT_PART.format(emotions=", ".join(EMOTIONS)))
        contract.append(AFFECT_CONTRACT)
    if intentions is not None:
        parts.append(INTENTIONS_PART.format(intentions=intentions))
        contract.append(INTENTIONS_CONTRACT)
    return "".join(parts) + "\nReply with a JSON object:\n{" + ",\n  ".join(contract) + "}"


def excerpt(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def render(trace, user_name: str) -> str:
    """One episode for the prompt: no signal, no generalization."""
    return (f"You were asked: “{excerpt(trace['situation'], K.TRACE_TEXT_CHARS)}”\n"
            f"  You answered like this: “{trace['reply']}”\n"
            f"  {user_name} replied: “{excerpt(trace['reaction'], K.TRACE_TEXT_CHARS)}” "
            f"({KIND_WORDS.get(trace['kind'], 'neutrally')})")


class TurnObserverV4(TurnObserver):
    """V3's per-turn observation with V2's reaction contract added (switch `traces`)."""

    def observe_all(self, session: Session, *, affect: bool, intentions: bool) -> dict | None:
        """Appraisal and intentions as V3 does them; returns the reaction with the messages it concerns, or None."""
        db = self.store.db
        rows = db.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 2", (session.id,)).fetchall()
        if len(rows) < 2 or rows[0]["role"] != "assistant" or rows[1]["role"] != "user":
            return None
        answer, user = rows[0], rows[1]
        prev = db.execute("SELECT * FROM messages WHERE session_id=? AND role='assistant' AND id<? ORDER BY id DESC "
                          "LIMIT 1", (session.id, user["id"])).fetchone()
        situation = db.execute("SELECT * FROM messages WHERE session_id=? AND role='user' AND id<? ORDER BY id DESC "
                               "LIMIT 1", (session.id, prev["id"])).fetchone() if prev else None
        open_ = self.intentions.open() if intentions else []
        listing = "\n".join(f"[{i.id}] {i.content}" for i in open_) or "(none)"
        dialog = (f"Alice's previous reply:\n{prev['content'][:4000]}\n\n" if prev
                  else "There is no previous reply (start of the conversation).\n\n")
        dialog += f"The user:\n{user['content']}\n\nAlice's answer:\n{answer['content'][:4000]}"
        try:
            data = self.llm.json(prompt(today_human(self.store.clock.now().date()), affect,
                                        listing if intentions else None), dialog, purpose="observe_v4", model=self.model)
        except Exception as e:
            log.warning("V4 observation failed: %s", e)
            return None
        log.info("observed (v4): %s", json.dumps(data, ensure_ascii=False)[:400])
        if affect and isinstance(data.get("feeling"), dict):
            f = data["feeling"]
            state = self.affect.update(clamp(f.get("valence"), f.get("arousal"), f.get("emotions")),
                                       cause=f"conversation: {user['content'][:120]}", message_id=answer["id"])
            new = [r[0] for r in db.execute(
                "SELECT id FROM memories WHERE source_session=? AND id NOT IN (SELECT memory_id FROM memory_affect)",
                (session.id,))]
            self.affect.tag(new, state)
        if intentions:
            known = {i.id for i in open_}
            for item in as_list(data.get("fulfilled"), dict):
                if (iid := as_int(item.get("id"))) in known:
                    self.intentions.fulfil(iid, message_id=answer["id"], answer=answer["content"],
                                           quote=str(item.get("quote") or ""))
            for item in as_list(data.get("commitments"), dict):
                self.intentions.add(str(item.get("content") or ""), due=item.get("due"), source="commitment",
                                    message_id=answer["id"], session_id=session.id)
        r = data.get("reaction")
        if prev is None or situation is None or not isinstance(r, dict):
            return None
        try:
            signal = max(-1.0, min(1.0, float(r.get("signal") or 0)))
        except (TypeError, ValueError):
            signal = 0.0
        kind = str(r.get("kind") or "neutral")
        return {"signal": signal, "kind": kind if kind in KINDS else "neutral", "what": str(r.get("what") or ""),
                "session_id": session.id, "situation": situation, "reply": prev, "reaction": user}


class TraceStore:
    def __init__(self, store: MemoryStore):
        self.store, self.db = store, store.db

    def add(self, r: dict, *, expected: float, pe: float, salience: float, call_id, vec) -> tuple[int, str]:
        """Returns (trace id, the text its node carries)."""
        situation, reply, reaction = r["situation"]["content"], r["reply"]["content"], r["reaction"]["content"]
        # the reply keeps its line breaks: its form (lists, length) is what a reaction is often about
        short = reply.strip()[:K.TRACE_REPLY_CHARS].rstrip() + ("…" if len(reply.strip()) > K.TRACE_REPLY_CHARS else "")
        row = {"situation": situation, "reply": short, "reaction": reaction, "kind": r["kind"]}
        trace_id = self.db.execute(
            "INSERT INTO v4_traces(session_id, situation_msg_id, reply_msg_id, reaction_msg_id, situation, reply, "
            "reaction, kind, what, signal, expected, pe, salience, llm_call_id, embedding, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (r["session_id"], r["situation"]["id"], r["reply"]["id"], r["reaction"]["id"], row["situation"],
             row["reply"], row["reaction"], r["kind"], r["what"], r["signal"], expected, pe, salience, call_id,
             vec.tobytes() if vec is not None else None, self.store.now())).lastrowid
        return trace_id, render(row, "The user")

    def get(self, ids) -> list:
        ids = list(ids)
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        by_id = {r["id"]: r for r in self.db.execute(f"SELECT * FROM v4_traces WHERE id IN ({q})", ids)}
        return [by_id[i] for i in ids if i in by_id]

    def signals(self) -> dict[int, float]:
        return {r[0]: r[1] for r in self.db.execute("SELECT id, signal FROM v4_traces")}


class TracesMechanism:
    """Under "From experience with <user>": the most active traces, chosen by the field before the reply."""

    def __init__(self, agent):
        self.agent = agent

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        a = self.agent
        ids = a._turn.get("trace_ids") or []
        if a._ablated("traces"):
            return None
        traces = a.traces.get(ids)
        if not traces:
            return None
        name = a.store.user_name()
        return Section(TITLE.format(name=name or "the user"),
                       "\n".join("- " + render(t, name or "The user") for t in traces),
                       FRAMING, {"trace_ids": [t["id"] for t in traces]})
