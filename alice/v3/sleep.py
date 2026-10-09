"""Sleep (spec §6.5; Alice7 mind/sleep.py): offline consolidation once a night, on the dialogue model.

1. NREM: near-duplicate fresh memories (by embeddings, no model) are merged into one when they are about the same
   thing. Written to V1's store through its API: originals are superseded, never deleted (spec D8).
2. REM: important older memories meet the fresh ones: causal and thematic links between shown ids, at most one
   insight (kept as the agent's own thought).
3. Lessons: duplicates merged, lessons contradicted by later evidence retired, others revised. V2's missing
   "step back" (article §4: lessons accumulated, almost none were retired).
4. Portrait of the day: V2's self-review contract with the day's thoughts as input.
The first reply after sleep carries what the agent woke up with.
"""

import json
import logging
from datetime import datetime

import numpy as np

from ..common.clock import iso
from ..common.llm import as_int, as_list
from ..common.text import today_human
from ..common.timefmt import ago
from ..v1.session import Session
from ..v2.context import Section
from ..v2.reflector import format_lessons, last_call_id
from ..v2.selfmodel import NOT_FIRST, FIRST_TIME, SELF_REVIEW_PROMPT

log = logging.getLogger(__name__)

CLUSTER_SIM = 0.82
REM_OLD, REM_FRESH = 6, 6
WOKE_TITLE = "## While you slept"
WOKE_FRAMING = "What you went over in your sleep last night."
WOKE_KEY = "v3_woke_with"   # meta: the last sleep's summary, shown at the start of the next conversation

NREM_PROMPT = """You are the memory of Alice, a conversational companion, during sleep: consolidating the day.
Below are groups of similar recent memories. For each group decide: merge them into one memory (if they are about
the same thing: repeats, refinements, parts of one fact) or keep them apart (if the differences matter). A merged
memory is one self-contained sentence that keeps everything important from the group and adds nothing.

Reply with a JSON object: {"groups": [{"group": int, "merge": bool, "content": str}]}"""

REM_PROMPT = """You are the memory of Alice, a conversational companion, during sleep: older memories meet recent ones.
Find what is really connected: what among the older ones led to or made possible a recent one (led_to), and what
is about the same thing from different sides (related). Don't force it: no link if there is none. If putting them
side by side shows something that wasn't visible before, state it as one insight, first person; otherwise null.

Reply with a JSON object:
{"links": [{"from": int, "to": int, "relation": "led_to|related"}], "insight": str | null}"""

LESSONS_PROMPT = """You are Alice, a conversational companion, going over your lessons in your sleep, with distance.
You see every active lesson with its history (when it was added, reinforced, weakened, and why). Tidy them:
- merge lessons that say the same thing (revise one to cover both, retire the other);
- retire a lesson that later evidence contradicts, rather than keeping both;
- revise a lesson whose wording drifted from what the evidence supports;
- leave the rest. Fewer, truer lessons are better than many.
Sleep brings no new evidence, so it doesn't make a lesson more or less certain: only the user's reactions do.

Reply with a JSON object:
{"ops": [{"op": "revise|retire", "id": int, "rule": str, "situation": str, "why": str}]}"""

# Without new reactions from the user, a lesson's confidence doesn't move (V3 pass 1: sleep and wakes reinforced
# a misread lesson eight times "with no contradicting evidence" and drove it to 0.95)
NO_EVIDENCE_OPS = ("revise", "retire")


def clusters(rows: list, threshold: float = CLUSTER_SIM) -> list[list]:
    """Greedy: each memory joins the first cluster whose seed is similar enough."""
    out: list[tuple[np.ndarray, list]] = []
    for r in rows:
        vec = np.frombuffer(r["embedding"], dtype=np.float32)
        for seed, members in out:
            if float(seed @ vec) >= threshold:
                members.append(r)
                break
        else:
            out.append((vec, [r]))
    return [members for _, members in out if len(members) > 1]


class Sleeper:
    def __init__(self, agent, model: str):
        self.agent, self.model = agent, model
        self.store, self.db, self.llm = agent.store, agent.db, agent.llm

    def _log(self, at: datetime, phase: str, summary: dict) -> int:
        return self.db.execute("INSERT INTO sleep_log(at, phase, summary) VALUES (?, ?, ?)",
                               (iso(at), phase, json.dumps(summary, ensure_ascii=False))).lastrowid

    def sleep(self, at: datetime, since: str) -> dict:
        woke_with = {"at": iso(at)}
        woke_with["merged"] = self._nrem(at, since)
        woke_with["linked"], woke_with["insight"] = self._rem(at, since)
        if self.agent.switches.lessons:
            woke_with["lessons"] = self._lessons(at)
        if self.agent.switches.selfmodel:
            woke_with["portrait"] = self._portrait(at, since)
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                        (WOKE_KEY, json.dumps(woke_with, ensure_ascii=False)))
        return woke_with

    # ---------- NREM ----------

    def _nrem(self, at: datetime, since: str) -> int:
        rows = self.db.execute("SELECT id, content, importance, tier, embedding FROM memories WHERE kind='fact' "
                               "AND valid_to IS NULL AND embedding IS NOT NULL AND created_at > ? ORDER BY id",
                               (since,)).fetchall()
        groups = clusters(rows)
        if not groups:
            self._log(at, "nrem", {"groups": 0, "merged": 0})
            return 0
        listing = "\n\n".join(f"Group {n}:\n" + "\n".join(f"- {r['content']}" for r in g) for n, g in enumerate(groups))
        try:
            data = self.llm.json(NREM_PROMPT, listing, purpose="sleep", model=self.model)
        except Exception as e:
            log.warning("NREM failed: %s", e)
            return 0
        merged = 0
        for item in as_list(data.get("groups"), dict):
            n, content = as_int(item.get("group")), str(item.get("content") or "").strip()
            if item.get("merge") is not True or n is None or not 0 <= n < len(groups) or not content:
                continue
            members = groups[n]
            ids = [r["id"] for r in members]
            entities = {self.store.entity_label(e) for e in self.store.memory_entity_ids(ids)}
            new_id = self.store.add_memory(content, importance=max(r["importance"] for r in members),
                                           tier="core" if any(r["tier"] == "core" for r in members) else "normal",
                                           entities=sorted(entities))
            for old in ids:
                if old != new_id:
                    self.store.supersede(old, new_id)
                    self.store.link_memories(new_id, old, "generalizes")
            merged += len(ids)
        self._log(at, "nrem", {"groups": len(groups), "merged": merged})
        return merged

    # ---------- REM ----------

    def _rem(self, at: datetime, since: str) -> tuple[int, str | None]:
        fresh = self.db.execute("SELECT id, content, valid_from FROM memories WHERE valid_to IS NULL AND created_at > ? "
                                "ORDER BY importance DESC, id LIMIT ?", (since, REM_FRESH)).fetchall()
        old = self.db.execute("SELECT id, content, valid_from FROM memories WHERE valid_to IS NULL AND created_at <= ? "
                              "ORDER BY importance DESC, access_count DESC, id LIMIT ?", (since, REM_OLD)).fetchall()
        if not fresh or not old:
            self._log(at, "rem", {"links": 0, "insight": None})
            return 0, None
        shown = {r["id"] for r in fresh} | {r["id"] for r in old}
        text = ("Older:\n" + "\n".join(f"[{r['id']}] ({ago(r['valid_from'], at)}) {r['content']}" for r in old)
                + "\n\nRecent:\n" + "\n".join(f"[{r['id']}] ({ago(r['valid_from'], at)}) {r['content']}" for r in fresh))
        try:
            data = self.llm.json(REM_PROMPT, text, purpose="sleep", model=self.model)
        except Exception as e:
            log.warning("REM failed: %s", e)
            return 0, None
        links = 0
        for link in as_list(data.get("links"), dict):
            src, dst = as_int(link.get("from")), as_int(link.get("to"))
            relation = link.get("relation") if link.get("relation") in ("led_to", "related") else None
            if src in shown and dst in shown and relation:
                self.store.link_memories(src, dst, relation)
                links += 1
        insight = data.get("insight") if isinstance(data.get("insight"), str) and data["insight"].strip() else None
        row = self._log(at, "rem", {"links": links, "insight": insight})
        if insight:
            self.agent.thoughts.add(insight, source="sleep", source_id=row)
        return links, insight

    # ---------- lessons ----------

    def _lessons(self, at: datetime) -> dict:
        lessons = self.agent.lessons.active()
        if len(lessons) < 2:
            self._log(at, "lessons", {"ops": 0})
            return {"ops": 0}
        lines = [format_lessons(lessons), "\nHistories:"]
        for l in lessons:
            lines.append(f"[{l.id}] " + "; ".join(f"{e['sim_ts'][:10]} {e['op']} ({e['note'][:80]})"
                                                 for e in self.agent.lessons.history(l.id)[-5:]))
        try:
            data = self.llm.json(LESSONS_PROMPT, "\n".join(lines), purpose="sleep", model=self.model)
        except Exception as e:
            log.warning("lesson sleep failed: %s", e)
            return {"ops": 0}
        before = self.db.execute("SELECT COALESCE(MAX(id), 0) FROM lesson_events").fetchone()[0]
        ops = [o for o in as_list(data.get("ops"), dict) if o.get("op") in NO_EVIDENCE_OPS]  # tidies, doesn't invent
        applied = self.agent.reflector.apply(ops, {l.id for l in lessons}, [], last_call_id(self.db, "sleep"))
        events = [r[0] for r in self.db.execute("SELECT id FROM lesson_events WHERE id > ?", (before,))]
        row = self._log(at, "lessons", {"ops": applied, "retired": sum(1 for o in ops if o.get("op") == "retire")})
        self.db.executemany("INSERT OR IGNORE INTO lesson_event_causes(event_id, source, source_id) VALUES (?, 'sleep', ?)",
                            [(e, row) for e in events])
        return {"ops": applied}

    # ---------- portrait of the day ----------

    def _portrait(self, at: datetime, since: str) -> bool:
        sm = self.agent.selfmodel
        previous = sm.current()
        thoughts = self.db.execute("SELECT content FROM thoughts WHERE at > ? ORDER BY id", (since,)).fetchall()
        episodes = self.db.execute("SELECT content FROM memories WHERE kind='episode' AND created_at > ? ORDER BY id",
                                   (since,)).fetchall()
        if not thoughts and not episodes:
            self._log(at, "portrait", {"changed": False})
            return False
        parts = []
        if previous:
            beliefs = "\n".join(f"[{b['id']}] ({b['weight']:.1f}) {b['text']}" for b in sm.beliefs(previous.id))
            parts.append(f"Your current portrait:\n{previous.content}\n\nYour current beliefs:\n{beliefs or '(none)'}")
        if episodes:
            parts.append("Today's conversations:\n" + "\n".join(f"- {e['content']}" for e in episodes))
        if thoughts:
            parts.append("What you thought on your own today:\n" + "\n".join(f"- {t['content']}" for t in thoughts))
        prompt = SELF_REVIEW_PROMPT.format(today=today_human(at.date()), first_time=FIRST_TIME if previous is None
                                           else NOT_FIRST, words=self.agent.v2.portrait_words, intentions_part="",
                                           intentions_contract="")
        prompt = prompt.replace("A conversation with the user has\njust ended", "The day is over")
        try:
            data = self.llm.json(prompt, "\n\n".join(parts), purpose="sleep", model=self.model)
        except Exception as e:
            log.warning("portrait of the day failed: %s", e)
            return False
        portrait = data.get("portrait")
        changed = isinstance(portrait, str) and bool(portrait.strip()) and (
            previous is None or portrait.strip() != previous.content)
        if changed:
            sm.save_portrait(portrait, changes=str(data.get("changes") or ""), beliefs=as_list(data.get("beliefs"), dict),
                             llm_call_id=last_call_id(self.db, "sleep"))
        self._log(at, "portrait", {"changed": changed})
        return changed


class SleepMechanism:
    """What the agent woke up with, at the start of the first conversation after sleep."""

    def __init__(self, agent):
        self.agent = agent

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        a = self.agent
        raw = a.db.execute("SELECT value FROM meta WHERE key=?", (WOKE_KEY,)).fetchone()
        if not raw or a.store.message_count(session.id) >= 2:
            return None
        woke = json.loads(raw[0])
        last_user = a.db.execute("SELECT MAX(ts) FROM messages WHERE role='user' AND session_id != ?",
                                 (session.id,)).fetchone()[0]
        if last_user and last_user > woke["at"]:
            return None  # already talked since that sleep
        lines = [f"You slept {ago(woke['at'], a.clock.now())}."]
        if woke.get("merged"):
            lines.append(f"You folded {woke['merged']} overlapping memories together.")
        if woke.get("linked"):
            lines.append(f"You connected {woke['linked']} older memories with recent ones.")
        if woke.get("insight"):
            lines.append(f"Something that became clear: {woke['insight']}")
        return Section(WOKE_TITLE, " ".join(lines), WOKE_FRAMING)
