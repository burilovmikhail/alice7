"""The wake (spec §6.4; Alice7 mind/wake.py): pressure crossed the threshold, the dialogue model thinks it through.

No one asked anything: a thought came by itself. The wake sees what accumulated (fresh experience, recent stream
thoughts, open intentions and questions, what is due) but no numbers. It may form an opinion, an intention or a
question, revise a lesson, resolve something, or write to the user first; or do nothing. Every wake is recorded
as productive (changed persistent state) or empty.
"""

import json
import logging
from datetime import datetime

from ..common.clock import iso
from ..common.llm import LLM, as_int, as_list
from ..common.text import today_human
from ..common.timefmt import ago
from ..v1.store import MemoryStore
from ..v2.reflector import format_lessons, last_call_id
from .affect import THOUGHT_WEIGHT, clamp, words
from .pressure import Pressure

log = logging.getLogger(__name__)

WAKE_PROMPT = """You are Alice, a conversational companion. Today is {today}. No one has asked you anything: a thought
came by itself. This is your own time: think through what has been building up.

{portrait}Then decide what to do with it. Doing nothing is fine; most thoughts need no action.
- opinion: a view you now hold on a topic (topic, content, stance -1..1; replaces: id of your earlier opinion on it).
- intention: something you want to do or bring up with the user later (content; due: YYYY-MM-DD or null).
- question: an open question you want to come back to.
- lesson: a change to how you talk or act with the user, with distance from the moment (op add|reinforce|weaken|
  revise|retire, as in your reflection: id, category, rule, situation, confidence).
- resolve: close an open question with an answer (question_id, answer), or drop an intention (intention_id, reason).
- write: send the user a message now, first, without being asked (content). {write_rule}
- feeling: how this thought leaves you (valence -1..1, arousal 0..1).

Reply with a JSON object:
{{"thought": str (first person, 2-6 sentences), "feeling": {{"valence": float, "arousal": float}},
  "do": [{{"type": "opinion|intention|question|lesson|resolve|write|nothing", ...}}]}}"""

WRITE_ALLOWED = ("Only if it would be welcome and you have a real reason, such as something you meant to do now "
                 "being due. Most of the time, don't.")
WRITE_BLOCKED = "Not possible right now."


class Waker:
    def __init__(self, agent, llm: LLM, model: str):
        self.agent, self.llm, self.model = agent, llm, model
        self.store: MemoryStore = agent.store
        self.db = agent.db

    def _context(self, p: Pressure, now: datetime) -> str:
        a, parts = self.agent, []
        last = self.db.execute("SELECT MAX(ts) FROM messages WHERE role='user'").fetchone()[0]
        parts.append(f"Now: {now:%A %Y-%m-%d %H:%M}. " + (f"The user last wrote {ago(last, now)}." if last
                                                          else "You haven't talked with the user yet."))
        if a.v3_switches.affect:
            parts.append(f"Your mood: {words(a.affect.current(now))}.")
        if p.fresh:
            mems = a.store.memories_by_ids(p.fresh[-12:])
            parts.append("What happened since you last thought on your own:\n" + "\n".join(
                f"- ({ago(m.valid_from, now)}) {m.content[:300]}" for m in mems.values()))
        if p.stream:
            q = ",".join("?" * len(p.stream[-6:]))
            rows = self.db.execute(f"SELECT at, content FROM stream_thoughts WHERE id IN ({q}) ORDER BY id",
                                   p.stream[-6:]).fetchall()
            parts.append("Thoughts that passed through your mind:\n" + "\n".join(f"- {r['content']}" for r in rows))
        open_i = [i for i in a.later.open() if datetime.fromisoformat(i.not_before) <= now]
        if open_i:
            parts.append("Your open intentions:\n" + "\n".join(
                f"[{i.id}] {i.content}" + (f" (due {i.due}{', DUE NOW' if i.id in p.due else ''})" if i.due else "")
                for i in open_i))
        questions = a.thoughts.open_questions()
        if questions:
            parts.append("Your open questions:\n" + "\n".join(f"[{q['id']}] {q['content']}" for q in questions))
        opinions = a.selfmodel.opinions()
        if opinions:
            parts.append("Your opinions:\n" + "\n".join(f"[{o['id']}] {o['topic']}: {o['content']}" for o in opinions[-8:]))
        if a.switches.lessons:
            parts.append(f"Your lessons:\n{format_lessons(a.lessons.active())}")
        return "\n\n".join(parts)

    def wake(self, p: Pressure) -> tuple[int, list[dict]]:
        """Returns (wake id, messages written first)."""
        a, now = self.agent, self.agent.clock.now()
        portrait = a.selfmodel.current() if a.switches.selfmodel else None
        write_blocked = a.initiative.blocked(now)
        system = WAKE_PROMPT.format(today=today_human(now.date()),
                                    portrait=f"Who you are, in your own words:\n{portrait.content}\n\n" if portrait else "",
                                    write_rule=WRITE_BLOCKED if write_blocked else WRITE_ALLOWED)
        wake_id = self.db.execute("INSERT INTO wakes(at, trigger) VALUES (?, ?)",
                                  (iso(now), json.dumps({"parts": p.parts, "fresh": p.fresh, "stream": p.stream,
                                                         "threads": p.threads, "due": p.due}))).lastrowid
        try:
            data = self.llm.json(system, self._context(p, now), purpose="wake", model=self.model,
                                 temperature=a.cfg.chat_temperature)
        except Exception as e:
            log.warning("wake failed: %s", e)
            data = {}
        call_id = last_call_id(self.db, "wake")
        changed, written, decisions = self._apply(data, wake_id, now, call_id, write_blocked is None)
        if p.stream:
            self.db.execute("UPDATE stream_thoughts SET consumed=1 WHERE id IN (%s)" % ",".join("?" * len(p.stream)),
                            p.stream)
        a.thoughts.considered([int(t.split(":")[1]) for t in p.threads if t.startswith("question:")], now)
        self.db.execute("UPDATE wakes SET thought=?, decisions=?, productive=?, llm_call_id=? WHERE id=?",
                        (str(data.get("thought") or ""), json.dumps(decisions, ensure_ascii=False), int(changed),
                         call_id, wake_id))
        log.info("wake #%s %s: %s", wake_id, "productive" if changed else "empty", str(data.get("thought"))[:200])
        return wake_id, written

    def _apply(self, data: dict, wake_id: int, now: datetime, call_id, may_write: bool):
        a = self.agent
        changed, written, decisions = False, [], []
        if thought := str(data.get("thought") or "").strip():  # kept, but a thought alone isn't a change of state
            a.thoughts.add(thought, source="wake", source_id=wake_id)
        if a.v3_switches.affect and isinstance(data.get("feeling"), dict):
            f = data["feeling"]
            a.affect.update(clamp(f.get("valence"), f.get("arousal"), {}), cause=f"own thought: {thought[:100]}",
                            weight=THOUGHT_WEIGHT)
        known_lessons = {l.id for l in a.lessons.active()}
        for d in as_list(data.get("do"), dict)[:6]:
            kind, done = d.get("type"), False
            if kind == "opinion" and a.switches.selfmodel:
                done = a.selfmodel.add_opinion(str(d.get("topic") or ""), str(d.get("content") or ""),
                                               d.get("stance"), replaces=d.get("replaces"), source="wake") is not None
            elif kind == "intention" and a._later_on():
                done = a.later.add(str(d.get("content") or ""), due=d.get("due"), source="wake") is not None
            elif kind == "question":
                done = a.thoughts.ask(str(d.get("content") or ""), source="wake", source_id=wake_id) is not None
            elif kind == "lesson" and a.switches.lessons:
                before = self.db.execute("SELECT COALESCE(MAX(id), 0) FROM lesson_events").fetchone()[0]
                done = a.reflector.apply([d], known_lessons, [], call_id) > 0
                self.db.executemany("INSERT OR IGNORE INTO lesson_event_causes(event_id, source, source_id) "
                                    "VALUES (?, 'wake', ?)", [(r[0], wake_id) for r in self.db.execute(
                                        "SELECT id FROM lesson_events WHERE id > ?", (before,))])
            elif kind == "resolve":
                if (qid := as_int(d.get("question_id"))) is not None:
                    done = a.thoughts.resolve(qid, str(d.get("answer") or ""))
                elif (iid := as_int(d.get("intention_id"))) is not None and a.later.get(iid):
                    a.later.drop(iid, str(d.get("reason") or "dropped on reflection"))
                    done = True
            elif kind == "write" and may_write:
                due_ids = [i.id for i in a.later.due(now)]
                if msg := a.initiative.write(str(d.get("content") or ""), wake_id=wake_id,
                                             intention_id=due_ids[0] if due_ids else None):
                    written.append(msg)
                    done = True
            decisions.append({**d, "applied": bool(done)})
            changed = changed or bool(done)
        return changed, written, decisions
