"""Write path: after each turn a cheap model pulls facts, entities and relations out of the fresh messages."""

import logging

from ..common.clock import Clock
from ..common.llm import LLM, as_int, as_list
from ..common.text import today_human
from .retrieval import search
from .store import USER, USER_ALIASES, MemoryStore

log = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are the long-term memory module of Alice, a conversational companion. Today is {today}.
You get a fresh fragment of the dialogue between the user and Alice, plus what is already known.
Extract only what is worth remembering for weeks and months: facts about the user and the people in their life,
events, plans, agreements, preferences, important knowledge, and what Alice herself said, promised or offered.
Skip small talk and anything already known.

Rules:
- Each fact is a self-contained third-person statement that makes sense without the dialogue. Name people by
  name ("Mikhail's sister Masha lives in Kazan"), not "the user". If the user's name isn't known yet, say "the user".
- Write facts in the language the user writes in. Don't translate.
- Convert relative dates ("tomorrow", "on Friday", «вчера») to absolute dates.
- Record Alice's own commitments and notable statements as facts ("Alice promised to ask Mikhail about the exam").
- Record stated preferences as facts, the way they were stated ("Mikhail prefers short answers"). Never turn
  anything into advice, instructions or rules for Alice's future behavior. Record what happened and what is true.
- core=true only for stable personal data: name, birthday, family, city, profession, durable preferences.
  Everything else core=false.
- importance: 0.2 trivial, 0.5 ordinary, 0.9 very important.
- supersedes: ids of known records that the new fact replaces or corrects (moved, changed jobs, plans changed).
- because: ids of known records the new fact GREW OUT OF: its cause or precondition ("decided to change jobs"
  <- "burned out on the project"). Thematic similarity is not causation. If the link is only thematic, leave it
  empty. Usually it is empty.
- entities of a fact: whom and what it is about. Use "USER" for the user and "Alice" for Alice herself.
- entities list: people, pets, places, organisations, topics, things. When you learn the user's name, include
  {{"name": "USER", "type": "person", "aliases": ["<the name>"]}}.
- relations between entities, e.g. {{"src": "Masha", "relation": "sister of", "dst": "USER"}}.
- Hypotheticals, "what if" questions, imagined scenes, jokes and role-play are not facts. Don't extract them.
- Never write summaries of the conversation itself ("Alice and Mikhail discussed..."): conversations are
  recorded separately as episodes, marked (episode) in the known list. A fact states something true about
  the user, the people and things in their life, or Alice's commitments.

Reply with a JSON object only:
{{"facts": [{{"content": str, "core": bool, "importance": float, "entities": [str], "supersedes": [int],
             "because": [int]}}],
  "entities": [{{"name": str, "type": "person|pet|place|org|topic|thing", "aliases": [str]}}],
  "relations": [{{"src": str, "relation": str, "dst": str}}]}}
If there is nothing to remember, return empty lists."""

SPEAKERS = {"user": "User", "assistant": "Alice"}


def _who(name) -> str | None:
    if not isinstance(name, str) or not name.strip():
        return None
    return USER if name.strip().lower() in USER_ALIASES else name.strip()


class Extractor:
    def __init__(self, store: MemoryStore, llm: LLM, clock: Clock):
        self.store, self.llm, self.clock = store, llm, clock

    def process_pending(self, session_id: int) -> None:
        messages = self.store.unprocessed_messages(session_id)
        if not messages:
            return
        with self.store.tracer.cause(messages[-1]["id"]):
            self._process(session_id, messages)

    def _process(self, session_id: int, messages: list) -> None:
        dialog = "\n".join(f"{SPEAKERS.get(m['role'], m['role'])}: {m['content']}" for m in messages)
        user_text = " ".join(m["content"] for m in messages if m["role"] == "user")
        # Similar in meaning + recent: a cause often doesn't resemble its effect but happened shortly before it
        found = search(self.store, user_text[-2000:], now=self.clock.now(), limit=12)
        self.store.tracer.retrieval(message_id=messages[-1]["id"], query=user_text[-2000:],
                                    hits=found.records(), purpose="extract")
        known, known_ids = [], set()
        for m in self.store.core_memories() + [h.memory for h in found.hits] + self.store.recent_memories(8):
            if m.id not in known_ids:
                known.append(m)
                known_ids.add(m.id)
        known_text = "\n".join(f"[{m.id}] ({m.kind}) {m.content}" for m in known) or "(nothing yet)"

        data = self.llm.json(EXTRACT_PROMPT.format(today=today_human(self.clock.now().date())),
                             f"Already known:\n{known_text}\n\nNew dialogue:\n{dialog}", purpose="extract")
        self.apply(data, session_id, known_ids)
        self.store.mark_processed([m["id"] for m in messages])

    def apply(self, data: dict, session_id: int | None, known_ids: set[int]) -> list[int]:
        store = self.store
        for e in as_list(data.get("entities"), dict):
            if name := _who(e.get("name")):
                aliases = [a for a in as_list(e.get("aliases"), str) if a.strip().lower() not in USER_ALIASES]
                store.upsert_entity(name, e.get("type") if isinstance(e.get("type"), str) else None, aliases)

        for r in as_list(data.get("relations"), dict):
            src, dst, rel = _who(r.get("src")), _who(r.get("dst")), r.get("relation")
            if src and dst and isinstance(rel, str):
                store.link_entities(src, rel, dst)

        written = []
        for f in as_list(data.get("facts"), dict):
            content = f.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            entities = [n for e in as_list(f.get("entities")) if (n := _who(e))]
            if f.get("core") and not entities:
                entities = [USER]  # a stable fact without a subject is about the user
            memory_id = store.add_memory(content, kind="fact", tier="core" if f.get("core") else "normal",
                                         importance=f.get("importance", 0.5), entities=entities,
                                         source_session=session_id)
            written.append(memory_id)
            for old_id in map(as_int, as_list(f.get("supersedes"))):
                # Only what the model was actually shown may be closed (guards against hallucinated ids)
                if old_id is not None and old_id in known_ids and old_id != memory_id:
                    store.supersede(old_id, memory_id)
            for cause_id in map(as_int, as_list(f.get("because"))):
                if cause_id is not None and cause_id in known_ids:
                    store.link_memories(cause_id, memory_id, "led_to")
        return written

