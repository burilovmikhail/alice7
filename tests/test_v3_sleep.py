"""V3 sleep: NREM merge into V1 memory, REM links and insight, lesson hygiene, portrait of the day, waking."""

import json
from datetime import datetime

from alice.common.clock import SimClock
from alice.v2.config import V2Config
from alice.v3.agent import AgentV3
from alice.v3.config import V3Config
from alice.v3.sleep import WOKE_TITLE, clusters

from conftest import FakeLLM, fake_embed, make_cfg, user_content

A = "Hannah lives in Glasgow with her two cats and a dog"
B = "Hannah lives in Glasgow with her two cats and dog Rex"
C = "Theo is allergic to walnuts and pecans"
D = "Theo is allergic to walnuts"


def make_v3(tmp_path, clock, llm):
    return AgentV3(make_cfg(), clock, tmp_path / "v3.db", llm=llm, embed=fake_embed, persona="P", sync_writes=True,
                   v2=V2Config(), v3=V3Config())


def sleep_llm(**over):
    def sleep(kwargs):
        system = kwargs["messages"][0]["content"]
        if "consolidating the day" in system:
            return {"groups": [{"group": 0, "merge": True, "content": "Hannah lives in Glasgow with two cats and a dog, Rex"},
                               {"group": 1, "merge": False, "content": ""}]}
        if "older memories meet recent" in system:
            return {"links": [{"from": 1, "to": 5, "relation": "led_to"}, {"from": 1, "to": 999, "relation": "led_to"}],
                    "insight": "Hannah's pets matter to Theo."}
        if "going over your lessons" in system:
            return {"ops": [{"op": "retire", "id": 2, "why": "contradicted later"},
                            {"op": "add", "rule": "Invented in sleep"}]}
        return {"portrait": "I am Alice; I have been thinking about Theo's family.", "changes": "the day",
                "beliefs": [{"text": "Family matters", "weight": 0.7}]}
    return FakeLLM({"sleep": sleep, **over})


def test_clusters():
    rows = [{"id": i, "embedding": fake_embed([t])[0].tobytes()} for i, t in enumerate([A, B, C, D, "Unrelated chess"])]
    assert [[r["id"] for r in g] for g in clusters(rows)] == [[0, 1], [2, 3]]


def test_a_night_of_sleep(tmp_path):
    clock = SimClock(datetime(2026, 1, 5, 21, 0))
    agent = make_v3(tmp_path, clock, sleep_llm())
    old = agent.store.add_memory("Theo adopted a dog last spring", importance=0.9)
    clock.set(datetime(2026, 1, 5, 21, 30))
    agent.db.execute("UPDATE memories SET created_at='2025-06-01T10:00:00' WHERE id=?", (old,))
    ids = [agent.store.add_memory(t, importance=0.7, tier="core" if t == B else "normal") for t in (A, B, C, D)]
    agent.lessons.add("style", "Answer in prose", confidence=0.7)
    agent.lessons.add("style", "Use bullet lists", confidence=0.6)
    agent.thoughts.add("Theo's family keeps coming up", source="wake", source_id=None)
    agent.advance(datetime(2026, 1, 6, 3, 0))

    phases = {r["phase"]: json.loads(r["summary"]) for r in agent.db.execute("SELECT * FROM sleep_log")}
    assert phases["nrem"] == {"groups": 2, "merged": 2}
    merged = [m for m in agent.store.all_memories() if "Rex" in m.content and "two cats" in m.content]
    assert len(merged) == 1 and merged[0].tier == "core"            # the core fact stays core
    gone = agent.store.memories_by_ids(ids[:2], active_only=False)
    assert all(m.superseded_by == merged[0].id for m in gone.values())  # superseded, not deleted
    assert agent.store.memories_by_ids(ids[2:])                     # walnuts kept apart: differences matter
    assert phases["rem"]["links"] == 1 and phases["rem"]["insight"] == "Hannah's pets matter to Theo."
    assert agent.db.execute("SELECT source FROM thoughts WHERE content LIKE 'Hannah%'").fetchone()[0] == "sleep"
    assert agent.lessons.get(2) is None and [l.rule for l in agent.lessons.active()] == ["Answer in prose"]
    cause = agent.db.execute("SELECT source FROM lesson_event_causes").fetchone()[0]
    assert cause == "sleep" and phases["lessons"] == {"ops": 1, "retired": 1}
    assert agent.selfmodel.current().content.startswith("I am Alice; I have been thinking")
    prompt = [k for p, k in agent.llm.requests if p == "sleep"][-1]["messages"][0]["content"]
    assert "The day is over" in prompt and prompt[:50] != ""
    agent.close()


def test_waking_up_and_own_thoughts_in_the_next_conversation(tmp_path):
    clock = SimClock(datetime(2026, 1, 5, 21, 0))
    llm = sleep_llm(chat="Good morning!")
    agent = make_v3(tmp_path, clock, llm)
    agent.store.add_memory("Theo adopted a dog last spring", importance=0.9)
    agent.db.execute("UPDATE memories SET created_at='2025-06-01T10:00:00'")
    for t in (A, B):
        agent.store.add_memory(t, importance=0.7)
    agent.advance(datetime(2026, 1, 6, 9, 0))
    agent.reply("Morning! Hannah's dog Rex is staying with us this week.")
    user = user_content(llm.prompts("chat")[-1])
    assert WOKE_TITLE in user and "Hannah's pets matter to Theo" in user
    assert agent.thoughts.relevant("Hannah's pets matter to Theo")[0]["source"] == "sleep"  # kept as its own thought
    agent.reply("He's very cute")
    assert WOKE_TITLE not in user_content(llm.prompts("chat")[-1])  # only at the start
    agent.close()
