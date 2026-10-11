"""Episodic memory: what happened, in order (tuning log, entry 8; decisions of 2026-10-11).

V1 keeps facts (semantic memory) and folds a whole conversation into one summary: the order inside it is lost, so
"where did we stop yesterday?" or "how many chapters have we read?" has nothing to stand on. Here every exchange is
an event with its time and place in the sequence; a long text the user shares (a chapter, a letter) is a passage.
Events are nodes in the field, chained to their neighbours and linked to the facts extracted from them, so recalling
one brings back what came before and after.

What stays word for word is decided at encoding, as with people (the opening of a novel that struck you): for a
passage, the paragraph closest to what the agent answered (what struck it) is kept verbatim when the moment was
charged (the appraisal's arousal or valence, or a strong reaction); otherwise its first and last lines. The whole
text stays in the message log, never deleted, but is not "remembered".
"""

import json
import re
from datetime import datetime

import numpy as np

from ..common.timefmt import ago
from ..v1.session import Session
from ..v2.context import Section
from . import constants as K

TITLE = "## What happened, in order"
FRAMING = ("Moments from your conversations as they happened, oldest first: what was said or shared, and what "
           "stayed with you word for word.")
HEADING = re.compile(r"^\s*((?:Глава|Chapter|Часть|Part)\s+[\dIVXLC]+[^\n]{0,60}|Пролог|Эпилог|Prologue|Epilogue)\s*$",
                     re.I | re.M)
RECENT = re.compile(r"\b(?:stopp?ed|left off|last time|where were we|so far|how (?:many|much)|"
                    r"останов\w*|в прошлый раз|в последний раз|на чём|на чем|сколько|до куда|докуда|прочитал\w*)\b",
                    re.I)


def excerpt(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n(?=\S)", text) if len(p.strip()) >= 40]
    return parts or [text.strip()]


class Episodes:
    def __init__(self, agent):
        self.agent = agent
        self.db = agent.db

    # ---------- encoding ----------

    def _arousal(self, reply_id: int) -> tuple[float, float]:
        row = self.db.execute("SELECT valence, arousal FROM affect_states WHERE layer='fast' AND message_id=? "
                              "ORDER BY id DESC LIMIT 1", (reply_id,)).fetchone()
        return (row["valence"], row["arousal"]) if row else (0.0, 0.0)

    def _verbatim(self, text: str, reply: str) -> str | None:
        """The paragraph of a passage closest to what the agent answered: what struck it."""
        store = self.agent.store
        parts = paragraphs(text)[:K.PASSAGE_MAX_PARAGRAPHS]
        if store.embed is None or len(parts) < 2:
            return excerpt(parts[0], K.VERBATIM_CHARS) if parts else None
        try:
            vecs = store.embed(parts + [reply[:2000]])
        except Exception:
            return None
        best = int(np.argmax(vecs[:-1] @ vecs[-1]))
        p = parts[best]
        return p if len(p) <= K.VERBATIM_CHARS else p[:K.VERBATIM_CHARS].rstrip() + "…"

    def record(self, user_msg, reply_msg) -> int | None:
        """One exchange becomes an event (or a passage). Returns the event id."""
        if self.db.execute("SELECT 1 FROM v4_events WHERE message_id=?", (user_msg["id"],)).fetchone():
            return None
        text, reply = user_msg["content"], reply_msg["content"] if reply_msg else ""
        name = self.agent.store.user_name() or "The user"
        passage = len(text) >= K.PASSAGE_CHARS
        valence, arousal = self._arousal(reply_msg["id"]) if reply_msg else (0.0, 0.0)
        verbatim = self._verbatim(text, reply) if passage and self.charged(arousal + abs(valence)) else None
        # (the aftermath can still make it charged: revisit(), when the user's reaction and the next exchange come)
        if passage:
            lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
            label = (f"{name} shared a passage ({len(text):,} characters), beginning “{excerpt(lines[0], 120)}” and "
                     f"ending “{excerpt(lines[-1], 120)}”")
        else:
            label = f"{name}: “{excerpt(text, K.EVENT_TEXT_CHARS)}”"
        if reply:
            label += f" — you: “{excerpt(reply, K.EVENT_REPLY_CHARS)}”"
        seq = self.db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM v4_events").fetchone()[0]
        return self.db.execute(
            "INSERT INTO v4_events(session_id, message_id, reply_id, at, kind, seq, label, verbatim, valence, arousal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_msg["session_id"], user_msg["id"], reply_msg["id"] if reply_msg else None, user_msg["ts"],
             "passage" if passage else "event", seq, label, verbatim, valence, arousal)).lastrowid

    def intensity(self, r) -> float:
        """How strong the moment was: the agent's appraisal of it, plus the aftermath, as significance often ripens
        after the moment for people: the user's reaction to the answer (|signal|) and the next exchange's appraisal."""
        own = r["arousal"] + abs(r["valence"])
        reaction = self.db.execute("SELECT MAX(ABS(signal)) FROM v4_traces WHERE reply_msg_id=?",
                                   (r["reply_id"],)).fetchone()[0] or 0.0
        nxt = self.db.execute("SELECT arousal + ABS(valence) FROM v4_events WHERE seq=?", (r["seq"] + 1,)).fetchone()
        return own + reaction + max(0.0, (nxt[0] if nxt else 0.0) - own)

    def revisit(self, event_id: int) -> bool:
        """A passage looked at again once its aftermath is known: if it is now among the charged ones and has no
        verbatim part yet, the paragraph that struck the agent is kept. Returns True if it was."""
        r = self.db.execute("SELECT * FROM v4_events WHERE id=?", (event_id,)).fetchone()
        if r is None or r["kind"] != "passage" or r["verbatim"] or not self.charged_row(r):
            return False
        text = self.db.execute("SELECT content FROM messages WHERE id=?", (r["message_id"],)).fetchone()[0]
        reply = self.db.execute("SELECT content FROM messages WHERE id=?", (r["reply_id"],)).fetchone() \
            if r["reply_id"] else None
        verbatim = self._verbatim(text, reply[0] if reply else "")
        if not verbatim:
            return False
        self.db.execute("UPDATE v4_events SET verbatim=? WHERE id=?", (verbatim, event_id))
        f = self.agent.substrate.field
        if (i := f.node_for("passage", event_id)) is not None:
            f.label[i] = r["label"] + f" — word for word: “{verbatim}”"
            self.db.execute("UPDATE v4_nodes SET label=? WHERE id=?", (f.label[i], int(f.ids[i])))
        return True

    def charged_row(self, r) -> bool:
        """Charged among the passages before it, by intensity with the aftermath."""
        past = [self.intensity(p) for p in self.db.execute("SELECT * FROM v4_events WHERE kind='passage' AND seq < ?",
                                                           (r["seq"],)).fetchall()]
        value = self.intensity(r)
        if len(past) < K.VERBATIM_MIN_HISTORY:
            return value >= K.VERBATIM_INTENSITY
        return value >= float(np.quantile(past, 1 - K.VERBATIM_TOP))

    def charged(self, intensity: float, before_seq: int | None = None) -> bool:
        """In the top share of the passages so far (or before `before_seq`): what moved it, relative to its own
        experience, as with people."""
        where = " AND seq < ?" if before_seq is not None else ""
        past = [r[0] for r in self.db.execute(f"SELECT arousal + ABS(valence) FROM v4_events WHERE kind='passage'{where}",
                                              (before_seq,) if before_seq is not None else ())]
        if len(past) < K.VERBATIM_MIN_HISTORY:
            return intensity >= K.VERBATIM_INTENSITY
        return intensity >= float(np.quantile(past, 1 - K.VERBATIM_TOP))

    def recheck_verbatim(self) -> tuple[int, int]:
        """Apply the rule (intensity with the aftermath, relative to the passages before) to passages encoded under
        an older one, in their order. Returns (dropped, added)."""
        f = self.agent.substrate.field
        dropped = added = 0
        for r in self.db.execute("SELECT * FROM v4_events WHERE kind='passage' ORDER BY seq").fetchall():
            if not r["verbatim"]:
                added += self.revisit(r["id"])
                continue
            if self.charged_row(r):
                continue
            self.db.execute("UPDATE v4_events SET verbatim=NULL WHERE id=?", (r["id"],))
            if (i := f.node_for("passage", r["id"])) is not None:
                f.label[i] = r["label"]
                self.db.execute("UPDATE v4_nodes SET label=? WHERE id=?", (r["label"], int(f.ids[i])))
            dropped += 1
        return dropped, added

    def missing(self) -> list[tuple]:
        """(user message, its reply) for every exchange without an event yet, oldest first (also the backfill)."""
        rows = self.db.execute(
            "SELECT u.*, (SELECT a.id FROM messages a WHERE a.session_id=u.session_id AND a.id>u.id "
            "AND a.role='assistant' ORDER BY a.id LIMIT 1) AS reply_id FROM messages u WHERE u.role='user' AND "
            "u.id NOT IN (SELECT message_id FROM v4_events) ORDER BY u.id").fetchall()
        out = []
        for u in rows:
            if u["reply_id"] is None:
                continue   # not answered yet
            reply = self.db.execute("SELECT * FROM messages WHERE id=?", (u["reply_id"],)).fetchone()
            out.append((u, reply))
        return out

    def get(self, ids) -> list:
        ids = list(ids)
        if not ids:
            return []
        q = ",".join("?" * len(ids))
        return self.db.execute(f"SELECT * FROM v4_events WHERE id IN ({q}) ORDER BY seq", ids).fetchall()

    def neighbours(self, seqs: set[int], width: int = 1) -> set[int]:
        return {s + d for s in seqs for d in range(-width, width + 1)}

    def select(self, preview: np.ndarray, text: str, early: bool, session_id: int | None) -> list[int]:
        """Which events the reply sees: the most active, with their neighbours; at the start of a conversation, or
        when asked where things stopped, how the previous conversation ended."""
        f = self.agent.substrate.field
        idx = [i for i in np.flatnonzero(f.mask("event", "passage")) if preview[i] >= K.EVENT_MIN_A]
        top = sorted(idx, key=lambda i: -preview[i])[:K.EVENTS_ACTIVE]
        ids = {f.ref[i] for i in top}
        seqs = {r["seq"] for r in self.get(ids)}
        if early or RECENT.search(text):   # how the last conversation ended, and the last thing read (a bookmark)
            prev = self.db.execute("SELECT seq FROM v4_events WHERE session_id != ? ORDER BY seq DESC LIMIT ?",
                                   (session_id or -1, K.EVENTS_LAST)).fetchall()
            seqs |= {r[0] for r in prev}
            bookmark = self.db.execute("SELECT id FROM v4_events WHERE kind='passage' ORDER BY seq DESC LIMIT 1"
                                       ).fetchone()
        else:
            bookmark = None
        seqs = self.neighbours(seqs) if seqs else set()
        ids = set()
        if seqs:
            q = ",".join("?" * len(seqs))
            ids = {r[0] for r in self.db.execute(f"SELECT id FROM v4_events WHERE seq IN ({q}) ORDER BY seq DESC LIMIT ?",
                                                 [*seqs, K.EVENTS_SHOWN])}
        if bookmark:
            ids.add(bookmark[0])   # the last thing read, always
        return sorted(ids)

    def counts(self) -> dict:
        row = self.db.execute("SELECT COUNT(*), MIN(at), MAX(at) FROM v4_events WHERE kind='passage'").fetchone()
        headings = []
        for (text,) in self.db.execute("SELECT m.content FROM v4_events e JOIN messages m ON m.id = e.message_id "
                                       "WHERE e.kind='passage' ORDER BY e.seq"):
            for h in HEADING.findall(text):
                h = " ".join(h.split())
                if h not in headings:
                    headings.append(h)
        return {"passages": row[0], "first": row[1], "last": row[2], "headings": headings}


class EpisodesMechanism:
    """Under "What happened, in order": the events chosen before the reply, oldest first."""

    def __init__(self, agent):
        self.agent = agent

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        a = self.agent
        ids = a._turn.get("event_ids") or []
        if not ids or a._ablated("episodic"):
            return None
        now = a.clock.now()
        rows = a.episodes.get(ids)
        blocks = []
        for r in rows:
            when = datetime.fromisoformat(r["at"])
            block = f"- [{when:%a %d %b, %H:%M}, {ago(when, now)}] {r['label']}"
            if r["verbatim"]:
                block += f"\n  What stayed with you, word for word: “{r['verbatim']}”"
            blocks.append(block)
        bookmark = a.db.execute("SELECT id FROM v4_events WHERE kind='passage' ORDER BY seq DESC LIMIT 1").fetchone()
        keep = bookmark[0] if bookmark else None
        while len(blocks) > 1 and sum(len(b) for b in blocks) > K.EVENTS_BUDGET:
            k = next((n for n, r in enumerate(rows) if r["id"] != keep), None)   # the oldest go first, not the
            if k is None:                                                         # last thing read (a bookmark)
                break
            blocks.pop(k)
            rows = rows[:k] + rows[k + 1:]
        c = a.episodes.counts()
        if c["passages"] and (RECENT.search(query) or any(r["kind"] == "passage" for r in rows)):
            note = (f"(All in all {a.store.user_name() or 'the user'} has shared {c['passages']} passages with you, "
                    f"the first {ago(c['first'], now)}, the last {ago(c['last'], now)}.")
            if c["headings"]:
                note += " Headings in them, in order: " + "; ".join(c["headings"]) + "."
            blocks.append(note + ")")
        return Section(TITLE, "\n".join(blocks), FRAMING, {"event_ids": [r["id"] for r in rows]})


__all__ = ["Episodes", "EpisodesMechanism", "json"]
