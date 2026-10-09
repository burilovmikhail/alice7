"""V3 affect (fast reaction, slow mood, tags) and intentions with "later"."""

import json
from datetime import datetime, timedelta

import pytest

from alice.common.clock import SimClock, parse_offset
from alice.v2.config import V2Config
from alice.v3 import affect as A
from alice.v3.agent import AgentV3
from alice.v3.config import V3Config
from alice.v3.switches import V3Switches

from conftest import START, FakeLLM, fake_embed, make_cfg, user_content


def make_v3(tmp_path, clock, llm, **kw):
    return AgentV3(make_cfg(), clock, tmp_path / "v3.db", llm=llm, embed=fake_embed, persona="P", sync_writes=True,
                   v2=V2Config(), v3=V3Config(), **kw)


def test_mood_and_fast_layer_relax_in_sim_time(tmp_path, clock):
    agent = make_v3(tmp_path, clock, FakeLLM())
    aff = agent.affect
    assert aff.mood().valence == pytest.approx(A.TEMPERAMENT.valence)
    aff.update(A.State(-0.9, 0.9, {"anxiety": 0.9}), cause="bad news")
    now = clock.now()
    assert aff.current(now).valence < -0.3 and aff.unsettled(now) > 0.5
    mood_now = aff.mood(now).valence
    assert mood_now < A.TEMPERAMENT.valence  # the mood absorbed a little
    assert aff.current(now + timedelta(hours=2)).valence == pytest.approx(mood_now, abs=0.01)  # fast relaxed
    a_week = aff.mood(now + timedelta(days=7)).valence
    assert mood_now < a_week < A.TEMPERAMENT.valence and abs(a_week - A.TEMPERAMENT.valence) == pytest.approx(
        abs(mood_now - A.TEMPERAMENT.valence) / 2, rel=0.01)  # half the way back in a week
    assert "anxi" in A.words(aff.current(now)) or "tense" in A.words(aff.current(now))
    agent.close()


def test_appraisal_rides_on_the_turn_and_shows_as_mood(tmp_path, clock):
    llm = FakeLLM({"observe_v3": {"feeling": {"valence": 0.8, "arousal": 0.7, "emotions": {"joy": 0.8, "zeal": 1}}},
                   "extract": {"facts": [{"content": "Theo passed his exam", "importance": 0.8}]}, "chat": "Congrats!"})
    agent = make_v3(tmp_path, clock, llm)
    agent.reply("I passed my exam!!")
    row = agent.db.execute("SELECT * FROM affect_states WHERE layer='fast'").fetchone()
    assert row["valence"] > 0.4 and json.loads(row["emotions"]) == pytest.approx({"curiosity": 0.12, "calm": 0.12,
                                                                                  "joy": 0.48}, abs=0.01)
    mid = agent.store.all_memories()[0].id
    assert agent.affect.arousal_of([mid])[mid] > 0.3          # the memory keeps the tone of its moment
    agent.reply("Thanks")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert A.MOOD_TITLE in system and A.MOOD_FRAMING in system
    prompt = llm.prompts("observe_v3")[0]["messages"][0]["content"]
    assert "feeling" in prompt and "commitments" in prompt
    agent.close()


def test_affect_off_means_no_appraisal_and_no_mood(tmp_path, clock):
    llm = FakeLLM({"observe_v3": {"feeling": {"valence": 0.8, "arousal": 0.7}}})
    agent = make_v3(tmp_path, clock, llm, v3_switches=V3Switches.parse("stream,wakes,sleep,initiative,later"))
    agent.reply("Hi")
    agent.reply("Hello?")
    assert agent.db.execute("SELECT COUNT(*) FROM affect_states").fetchone()[0] == 0
    assert A.MOOD_TITLE not in llm.prompts("chat")[-1]["messages"][0]["content"]
    assert "feeling" not in llm.prompts("observe_v3")[0]["messages"][0]["content"]
    agent.close()


def test_intention_is_not_fulfilled_in_the_conversation_that_made_it(tmp_path):
    """V2's E7 failure, replayed: the agent reminds at once and the observer reports it fulfilled."""
    clock = SimClock(datetime(2026, 6, 8, 20, 0))
    remind = "Oh, and don't forget to send Mrs Okafor that thank-you email!"
    llm = FakeLLM({"observe_v3": [
        {"commitments": [{"content": "Remind Clara to send Mrs Okafor a thank-you email", "due": None}]},
        {"fulfilled": [{"id": 1, "quote": "don't forget to send Mrs Okafor that thank-you email"}]},  # same session
        {"fulfilled": [{"id": 1, "quote": "something Alice never said"}]},                              # bad quote
        {"fulfilled": [{"id": 1, "quote": "don't forget to send Mrs Okafor that thank-you email"}]},
    ], "chat": [ "Sure, I'll remind you next time.", remind, remind, remind], "episode": {"summary": "x"}})
    agent = make_v3(tmp_path, clock, llm)
    agent.reply("Next time we talk, please remind me to send Mrs Okafor a thank-you email.")
    agent.reply("Thanks! Off to sleep now.")
    assert agent.later.get(1).status == "open"                  # too early: still the same conversation
    assert not agent.db.execute("SELECT COUNT(*) FROM intentions").fetchone()[0]  # V2's table is not used
    clock.advance(parse_offset("2d"))
    agent.reply("Hi! What a week.")
    user = user_content(llm.prompts("chat")[-1])
    assert "## On your mind" in user and "thank-you email" in user
    assert agent.later.get(1).status == "open"                  # the quote isn't in the answer
    agent.reply("Any ideas for tonight?")
    i = agent.later.get(1)
    assert i.status == "done"
    assert agent.db.execute("SELECT evidence FROM intentions_v3 WHERE id=1").fetchone()[0].startswith("don't forget")
    agent.close()


def test_due_intentions(tmp_path, clock):
    agent = make_v3(tmp_path, clock, FakeLLM())
    a = agent.later.add("Ask how the interview went", due=(START + timedelta(days=3)).date().isoformat(),
                        source="commitment")
    agent.later.add("Recommend a book", source="wake")
    assert agent.later.due(START) == []
    assert [i.id for i in agent.later.due(START + timedelta(days=3, hours=1))] == [a]
    agent.close()


def test_without_later_v2_intentions_work_as_in_v2(tmp_path, clock):
    llm = FakeLLM({"observe": {"commitments": [{"content": "Ask about the exam", "due": None}]}})
    agent = make_v3(tmp_path, clock, llm, v3_switches=V3Switches.parse("affect"))
    agent.reply("I have an exam on Friday")
    assert agent.intentions.open() and not agent.later.open()
    agent.close()
