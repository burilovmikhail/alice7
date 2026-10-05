"""Short-term memory (verbatim buffer + rolling summary) and turning a finished session into an episode."""

import logging
from datetime import datetime

from ..common.clock import Clock
from ..common.config import Config
from ..common.db import get_meta, set_meta
from ..common.llm import LLM, as_int, as_list
from ..common.timefmt import ago
from .store import MemoryStore

log = logging.getLogger(__name__)

FOLD_PROMPT = """You keep a brief running summary of the current conversation between the user and Alice.
Update the summary with the new messages. Keep the essentials: topics, questions, decisions, important details,
emotional tone. At most 150 words, in the language of the conversation. Return only the summary text."""

EPISODE_PROMPT = """Write a record of a finished conversation for Alice's long-term memory: what was discussed,
what important happened or came to light, agreements, what Alice did or said (including promises), and the
user's mood as observed. 2-5 sentences, third person, in the language of the conversation. Record what happened;
don't derive rules for future behavior.

continues: ids of earlier conversations this one GREW OUT OF: it continued a started topic, developed a thought,
returned to an agreement, or was made possible by them. Not just a similar topic. Usually 0-2.

Reply with a JSON object:
{"summary": str, "importance": float from 0 to 1, "entities": [names of people, places, topics], "continues": [int]}"""

SPEAKERS = {"user": "User", "assistant": "Alice"}


def _buffer_key(session_id: int) -> str:
    return f"buffer_from:{session_id}"


class Session:
    """The current conversation. The last N messages verbatim, everything older in the rolling summary."""

    def __init__(self, store: MemoryStore, llm: LLM, cfg: Config, session_id: int, summary: str = "",
                 buffer: list[dict] | None = None):
        self.store, self.llm, self.cfg = store, llm, cfg
        self.id = session_id
        self.summary = summary
        self.buffer: list[dict] = buffer or []

    @classmethod
    def start(cls, store: MemoryStore, llm: LLM, cfg: Config) -> "Session":
        """A new session always starts with an empty buffer: a true context reset."""
        return cls(store, llm, cfg, store.start_session())

    @classmethod
    def resume(cls, store: MemoryStore, llm: LLM, cfg: Config, session_id: int) -> "Session":
        """After a restart or in a probe fork: summary + exactly the messages that were in the buffer."""
        info = store.session_info(session_id)
        start = int(get_meta(store.db, _buffer_key(session_id), "0"))
        buffer = [{"id": m["id"], "role": m["role"], "content": m["content"]}
                  for m in store.session_messages(session_id, from_id=start)]
        return cls(store, llm, cfg, session_id, info["summary"] or "", buffer)

    def add(self, role: str, content: str, context_ids=()) -> int:
        message_id = self.store.add_message(self.id, role, content, context_ids)
        self.buffer.append({"id": message_id, "role": role, "content": content})
        return message_id

    def history(self) -> list[dict]:
        return [{"role": m["role"], "content": m["content"]} for m in self.buffer]

    def maybe_fold(self) -> None:
        limit = self.cfg.short_term
        if len(self.buffer) <= limit:
            return
        keep = max(limit // 2, 1)
        old, rest = self.buffer[:-keep], self.buffer[-keep:]
        transcript = "\n".join(f"{SPEAKERS.get(m['role'], m['role'])}: {m['content']}" for m in old)
        try:
            summary = self.llm.complete(
                FOLD_PROMPT, f"Current summary:\n{self.summary or '(empty)'}\n\nNew messages:\n{transcript}",
                purpose="fold")
        except Exception as e:
            log.warning("fold failed, will retry next turn: %s", e)  # messages stay in the buffer
            return
        if not summary:
            return
        self.summary, self.buffer = summary, rest
        self.store.set_session_summary(self.id, summary)
        set_meta(self.store.db, _buffer_key(self.id), rest[0]["id"])


def finalize_session(store: MemoryStore, llm: LLM, clock: Clock, session_id: int) -> int | None:
    """The session is over: store it as an episode linked to the facts learned in it. Returns the episode id."""
    info = store.session_info(session_id)
    if info is None:
        return None
    messages = store.session_messages(session_id)
    if not messages:
        store.delete_session(session_id)
        return None

    transcript = "\n".join(f"{SPEAKERS.get(m['role'], m['role'])}: {m['content']}" for m in messages)[-12000:]
    earlier = store.recent_episodes(6)
    now = clock.now()
    earlier_text = "\n".join(f"[{e.id}] {ago(e.valid_from, now)}: {e.content}" for e in earlier) or "(none)"
    with store.tracer.cause(messages[-1]["id"]):
        try:
            data = llm.json(EPISODE_PROMPT,
                            f"Earlier conversations:\n{earlier_text}\n\n"
                            f"Summary of the beginning of this conversation:\n{info['summary'] or '(none)'}\n\n"
                            f"Messages:\n{transcript}", purpose="episode")
        except Exception as e:
            log.warning("episode for session %s failed: %s", session_id, e)
            data = {}
        summary = data.get("summary") if isinstance(data.get("summary"), str) else ""
        if not summary.strip():
            log.warning("no episode for session %s", session_id)
            store.end_session(session_id, None)
            return None

        started = datetime.fromisoformat(info["started_at"])
        episode_id = store.add_memory(f"Conversation on {started:%Y-%m-%d %H:%M}: {summary.strip()}",
                                      kind="episode", importance=data.get("importance", 0.5),
                                      entities=as_list(data.get("entities"), str), valid_from=info["started_at"],
                                      source_session=session_id)
        for fact_id in store.session_memory_ids(session_id):
            store.link_memories(episode_id, fact_id, "contains")
        earlier_ids = {e.id for e in earlier}
        for prev_id in map(as_int, as_list(data.get("continues"))):
            if prev_id in earlier_ids:
                store.link_memories(prev_id, episode_id, "led_to")
        store.end_session(session_id, summary.strip())
    return episode_id
