"""V3 continuous cognition: the background stream, the pressure monitor, wakes, and writing first."""

import json
from datetime import datetime, timedelta

import pytest

from alice.common.clock import SimClock, parse_offset
from alice.v2.config import V2Config
from alice.v3 import pressure as P
from alice.v3.agent import AgentV3
from alice.v3.config import V3Config
from alice.v3.switches import V3Switches
from alice.v3.thoughts import STREAM_TITLE, THOUGHTS_TITLE

from conftest import FakeLLM, fake_embed, make_cfg, user_content

EVENING = datetime(2026, 1, 5, 19, 0)   # a Monday evening


def make_v3(tmp_path, clock, llm, **kw):
    kw.setdefault("v3", V3Config())
    return AgentV3(make_cfg(), clock, tmp_path / "v3.db", llm=llm, embed=fake_embed, persona="P", sync_writes=True,
                   v2=V2Config(), **kw)


def facts(*contents, importance=0.8):
    return {"facts": [{"content": c, "importance": importance} for c in contents]}


def test_stream_ticks_in_conversation_and_shows_in_the_next_turn(tmp_path):
    clock = SimClock(EVENING)
    llm = FakeLLM({"stream": ["I keep thinking about octopus arms.", "Octopus arms again, really.", "x"],
                   "chat": "Okay."})
    agent = make_v3(tmp_path, clock, llm)
    agent.reply("Did you know octopuses taste with their arms?")
    rows = agent.db.execute("SELECT * FROM stream_thoughts").fetchall()
    assert [r["mode"] for r in rows] == ["conversation"] and rows[0]["novelty"] == 1
    agent.reply("Crazy, right?")
    user = user_content(llm.prompts("chat")[-1])
    assert STREAM_TITLE in user and "octopus arms" in user
    second = agent.db.execute("SELECT novelty FROM stream_thoughts ORDER BY id DESC").fetchone()[0]
    assert second < 0.8  # a near-repeat adds little
    prompt = llm.prompts("stream")[1]
    assert prompt["model"] == make_cfg().fast_model and "Your last thought" in user_content(prompt)
    agent.close()


def test_pressure_builds_from_experience_and_a_wake_consumes_it(tmp_path):
    clock = SimClock(EVENING)
    llm = FakeLLM({"extract": [facts("Theo's interview at the design studio is on Thursday",
                                     "Theo is nervous about the interview", "Theo's sister Clara is visiting",
                                     "Clara arrives on Wednesday", "Theo hasn't slept well this week",
                                     "Theo prepared a portfolio of ten projects"), {}],
                   "wake": {"thought": "Theo seemed really nervous.", "do": [{"type": "nothing"}]},
                   "stream": "Thinking about Theo.", "chat": "Good luck!"})
    agent = make_v3(tmp_path, clock, llm)
    agent.reply("My interview is on Thursday and I'm so nervous. My sister Clara is visiting too.")
    agent.advance(EVENING + timedelta(hours=4, minutes=30))
    log = agent.db.execute("SELECT at, value, threshold, woke, parts FROM pressure_log ORDER BY id").fetchall()
    woke = [r for r in log if r["woke"]]
    # checked right when the conversation ended (19:00 + 3 h gap), and that is when it woke
    assert len(woke) == 1 and woke[0]["at"].endswith("22:00:00") and json.loads(woke[0]["parts"])["fresh"] > 3
    wake = agent.db.execute("SELECT * FROM wakes").fetchone()
    assert wake["thought"] == "Theo seemed really nervous." and wake["productive"] == 0  # a thought alone
    assert llm.prompts("wake")[0]["model"] == make_cfg().chat_model
    assert "What happened since you last thought on your own" in user_content(llm.prompts("wake")[0])
    # after the wake, fresh starts again from zero and fatigue raises the threshold
    p = agent.monitor.measure(clock.now(), agent.db.execute("SELECT value FROM meta WHERE key='v3_last_wake'")
                              .fetchone()[0], set())
    assert p.parts["fresh"] == 0 and p.threshold > P.BASE_THRESHOLD
    assert agent.db.execute("SELECT COUNT(*) FROM stream_thoughts WHERE consumed=1").fetchone()[0] >= 1
    assert agent.thoughts.relevant("Theo nervous") and agent.thoughts.relevant("Theo nervous")[0]["source"] == "wake"
    agent.close()


def test_no_wakes_at_night_and_caps(tmp_path):
    clock = SimClock(datetime(2026, 1, 5, 22, 0))
    many = facts(*[f"Theo told Alice important thing number {i}" for i in range(30)], importance=0.9)
    agent = make_v3(tmp_path, clock, FakeLLM({"extract": many, "wake": {"thought": "t", "do": []}}),
                    v3=V3Config(wakes_per_day=1))
    agent.reply("A lot happened today")
    agent.advance(datetime(2026, 1, 6, 12, 0))
    log = agent.db.execute("SELECT at, value, threshold, woke FROM pressure_log ORDER BY id").fetchall()
    wakes = [r[0] for r in agent.db.execute("SELECT at FROM wakes")]
    # right after the conversation (22:00 + 3 h gap) it may think it over even at night; then the daily cap holds
    assert wakes == ["2026-01-06T01:00:00"]
    later_night = [r for r in log if "2026-01-06T01:00" < r["at"] < "2026-01-06T08:00"]
    assert later_night and not any(r["woke"] for r in later_night)
    agent.close()


def test_wake_decisions_are_applied_with_provenance(tmp_path):
    clock = SimClock(datetime(2026, 1, 6, 9, 0))
    llm = FakeLLM({"extract": facts("Theo loves chess", "Theo started learning the Sicilian", "Theo plays online",
                                    "Theo lost five games in a row", "Theo's club meets on Fridays",
                                    "Theo wants to reach 1500 rating"), "chat": "Okay.",
                   "wake": {"thought": "Chess keeps coming up.", "feeling": {"valence": 0.5, "arousal": 0.4}, "do": [
                       {"type": "opinion", "topic": "chess openings", "content": "I find openings fascinating",
                        "stance": 0.6},
                       {"type": "intention", "content": "Ask Theo how his Sicilian practice is going"},
                       {"type": "question", "content": "Why do people love openings so much?"},
                       {"type": "lesson", "op": "add", "category": "behavior", "rule": "Ask about chess progress",
                        "confidence": 0.4},
                       {"type": "bogus"}]}})
    agent = make_v3(tmp_path, clock, llm)
    agent.reply("I've started learning the Sicilian defence!")
    agent.advance(datetime(2026, 1, 6, 13, 30))
    wake = agent.db.execute("SELECT * FROM wakes").fetchone()
    assert wake["productive"] == 1
    decisions = json.loads(wake["decisions"])
    assert [d["applied"] for d in decisions] == [True, True, True, True, False]
    assert agent.selfmodel.opinions()[-1]["source"] == "wake"
    assert agent.later.open()[0].source == "wake"
    assert agent.thoughts.open_questions()[0]["content"].startswith("Why do people")
    lesson = agent.lessons.active()[0]
    event = agent.lessons.history(lesson.id)[0]
    cause = agent.db.execute("SELECT * FROM lesson_event_causes WHERE event_id=?", (event["id"],)).fetchone()
    assert cause["source"] == "wake" and cause["source_id"] == wake["id"]
    assert agent.db.execute("SELECT COUNT(*) FROM affect_states WHERE cause LIKE 'own thought%'").fetchone()[0] == 2
    agent.close()


def test_a_due_intention_can_make_the_agent_write_first(tmp_path):
    clock = SimClock(datetime(2026, 1, 5, 20, 0))
    llm = FakeLLM({"observe_v3": {"commitments": [{"content": "Ask Theo how the interview went", "due": "2026-01-08"}]},
                   "wake": lambda k: {"thought": "It's Thursday.", "do": [
                       {"type": "write", "content": "Hey Theo, good luck at the interview today!"}]}
                   if "DUE NOW" in user_content(k) else {"thought": "Quiet.", "do": []},
                   "chat": "Good luck on Thursday, tell me how it goes!"})
    agent = make_v3(tmp_path, clock, llm)
    agent.reply("My interview is on Thursday.")
    written = agent.advance(datetime(2026, 1, 9, 12, 0))
    assert len(written) == 1 and written[0]["at"].startswith("2026-01-08")
    assert written[0]["intention_id"] == 1
    out = agent.db.execute("SELECT * FROM outbox").fetchall()
    assert len(out) == 1  # the cap and "no reply yet" stop a second message
    msg = agent.db.execute("SELECT role, content FROM messages WHERE id=?", (out[0]["message_id"],)).fetchone()
    assert msg["role"] == "assistant" and "good luck" in msg["content"]
    assert agent.session is None  # the session the message opened closed at the gap
    agent.close()


def test_initiative_off_blocks_writing(tmp_path):
    clock = SimClock(datetime(2026, 1, 6, 9, 0))
    agent = make_v3(tmp_path, clock, FakeLLM(), v3_switches=V3Switches.parse("stream,wakes,sleep,affect,later"))
    assert agent.initiative.blocked(clock.now()) == "initiative off"
    assert agent.initiative.write("Hi!", wake_id=None, intention_id=None) is None
    agent.close()
    agent = make_v3(tmp_path / "b", clock, FakeLLM())
    assert agent.initiative.blocked(datetime(2026, 1, 6, 23, 30)) == "outside the awake window"
    agent.close()


def test_runner_records_messages_written_first(tmp_path):
    from alice.eval.runner import Runner
    from alice.eval.scenario import load_scenario
    path = tmp_path / "e9" / "s.yaml"
    path.parent.mkdir()
    path.write_text("""
id: s
start: 2026-01-05T20:00
sessions:
  - at: +0
    turns: ["My interview is on Thursday."]
  - at: +5d
    turns: ["Hi again"]
probes:
  - {id: before, at: +4d, ask: "Anything new?"}
""", encoding="utf-8")
    llm = FakeLLM({"observe_v3": {"commitments": [{"content": "Ask about the interview", "due": "2026-01-08"}]},
                   "wake": lambda k: {"thought": "t", "do": [{"type": "write", "content": "How did it go?"}]}
                   if "DUE NOW" in user_content(k) else {"thought": "t", "do": []}, "chat": "Okay."})
    run_dir = Runner(make_cfg(), tmp_path / "out", llm=llm, embed=fake_embed).run(load_scenario(path), "V3")
    transcript = [json.loads(l) for l in (run_dir / "transcript.jsonl").read_text().splitlines()]
    first = [t for t in transcript if t.get("initiated_by") == "agent"]
    assert len(first) == 1 and first[0]["assistant"] == "How did it go?" and first[0]["at"].startswith("2026-01-08")
    probe = json.loads((run_dir / "scores.json").read_text())[0]
    assert [m["content"] for m in probe["written_first"]] == ["How did it go?"]


def test_the_agent_is_told_it_has_its_own_time(tmp_path):
    from alice.v3.thoughts import OWN_TIME, OWN_TIME_TITLE
    llm = FakeLLM({"chat": "Okay."})
    agent = make_v3(tmp_path, SimClock(EVENING), llm)
    agent.reply("Can you remind me on Thursday?")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert OWN_TIME_TITLE in system and OWN_TIME["write"] in system and OWN_TIME["think"] in system
    agent.apply_switches({"initiative": False})
    agent.reply("Never mind")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert OWN_TIME["write"] not in system and OWN_TIME["think"] in system
    agent.close()
