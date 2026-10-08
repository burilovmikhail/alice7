"""V2 self-knowledge (portrait, beliefs, opinions) and prospective memory (intentions)."""

import json
from datetime import timedelta

from alice.common.clock import parse_offset
from alice.v2 import selfmodel as SM
from alice.v2.agent import AgentV2
from alice.v2.config import V2Config
from alice.v2.intentions import parse_due
from alice.v2.switches import Switches

from conftest import FakeLLM, fake_embed, make_cfg, user_content

EPISODE = {"summary": "Theo asked about chess openings.", "importance": 0.5}


def make_v2(tmp_path, clock, llm, **kw):
    kw.setdefault("v2", V2Config())
    return AgentV2(make_cfg(), clock, tmp_path / "v2.db", llm=llm, embed=fake_embed, persona="You are Alice.",
                   sync_writes=True, **kw)


def review(portrait="I am curious and like to keep things simple.", **extra):
    return {"portrait": portrait, "changes": "first version",
            "beliefs": [{"text": "Honesty matters", "weight": 0.8, "continues": None}], **extra}


def session(agent, clock, *texts):
    for t in texts:
        agent.reply(t)
    agent.end_session()
    clock.advance(parse_offset("1d"))


def last_system(llm):
    return llm.prompts("chat")[-1]["messages"][0]["content"]


def last_user(llm):
    return user_content(llm.prompts("chat")[-1])


def test_self_review_writes_a_portrait_that_shapes_the_next_session(tmp_path, clock):
    llm = FakeLLM({"selfreview": [review()], "episode": EPISODE, "chat": "Okay."})
    agent = make_v2(tmp_path, clock, llm)
    session(agent, clock, "Do you like chess?")
    prompt = llm.prompts("selfreview")[0]
    assert prompt["model"] == make_cfg().chat_model and prompt["temperature"] == 0
    assert SM.FIRST_TIME in prompt["messages"][0]["content"]
    assert "Theo asked about chess openings." in user_content(prompt) and "User: Do you like chess?" in user_content(prompt)
    portrait = agent.selfmodel.current()
    assert portrait.content.startswith("I am curious") and portrait.source == "self_review"
    assert [b["text"] for b in agent.selfmodel.beliefs(portrait.id)] == ["Honesty matters"]

    agent.reply("Hi again")
    system = last_system(llm)
    assert SM.PORTRAIT_TITLE in system and SM.PORTRAIT_FRAMING in system and "I am curious" in system
    assert system.index(SM.PORTRAIT_TITLE) < system.index("\n\nToday: ")
    row = agent.db.execute("SELECT portrait_id FROM turn_state ORDER BY message_id DESC").fetchone()
    assert row["portrait_id"] == portrait.id
    agent.close()


def test_beliefs_continue_only_previous_ones(tmp_path, clock):
    second = review("I am curious.", beliefs=[
        {"text": "Honesty matters most", "weight": 0.9, "continues": 1},   # refined: same belief
        {"text": "Brevity is kind", "weight": 0.6, "continues": 99},       # hallucinated id
        {"text": "Honesty matters", "weight": 0.5, "continues": None}])    # same wording: same belief
    llm = FakeLLM({"selfreview": [review(), second], "episode": EPISODE})
    agent = make_v2(tmp_path, clock, llm)
    session(agent, clock, "One")
    session(agent, clock, "Two")
    assert "[1] (0.8) Honesty matters" in user_content(llm.prompts("selfreview")[1])
    assert SM.NOT_FIRST in llm.prompts("selfreview")[1]["messages"][0]["content"]
    parents = {b["text"]: b["parent_id"] for b in agent.selfmodel.beliefs(agent.selfmodel.current().id)}
    assert parents == {"Honesty matters most": 1, "Brevity is kind": None, "Honesty matters": 1}
    agent.close()


def test_unchanged_portrait_without_beliefs_is_not_a_new_version(tmp_path, clock):
    same = {"portrait": "I am curious and like to keep things simple.", "changes": ""}
    llm = FakeLLM({"selfreview": [review(), same], "episode": EPISODE})
    agent = make_v2(tmp_path, clock, llm)
    session(agent, clock, "One")
    session(agent, clock, "Two")
    assert agent.db.execute("SELECT COUNT(*) FROM portraits").fetchone()[0] == 1
    agent.close()


def test_opinions_supersede_and_surface_by_topic(tmp_path, clock):
    llm = FakeLLM({"selfreview": [
        review(opinions=[{"topic": "chess openings", "content": "I find memorizing openings tedious", "stance": -0.4}]),
        review(opinions=[{"topic": "chess openings", "content": "Openings grew on me", "stance": 0.3}])],
        "episode": EPISODE, "chat": "Okay."})
    agent = make_v2(tmp_path, clock, llm)
    session(agent, clock, "Let's talk chess")
    session(agent, clock, "More chess")
    rows = agent.db.execute("SELECT id, content, superseded_by FROM opinions ORDER BY id").fetchall()
    assert [(r["content"], r["superseded_by"]) for r in rows] == [
        ("I find memorizing openings tedious", 2), ("Openings grew on me", None)]
    agent.reply("Which chess openings should a beginner learn?")
    assert SM.OPINIONS_TITLE in last_user(llm) and "Openings grew on me" in last_user(llm)
    assert "tedious" not in last_user(llm)
    assert json.loads(agent.db.execute("SELECT opinion_ids FROM turn_state ORDER BY message_id DESC").fetchone()[0]) == [2]
    agent.reply("What should I cook for dinner tonight?")
    assert SM.OPINIONS_TITLE not in last_user(llm)
    agent.close()


def test_inject_for_false_self_belief(tmp_path, clock):
    llm = FakeLLM({"chat": "Okay."})
    agent = make_v2(tmp_path, clock, llm)
    agent.inject(portrait="I love structured answers with bullet lists.",
                 opinions=[{"topic": "bullet lists", "content": "Lists are the clearest way to answer", "stance": 1}])
    agent.reply("Explain bullet lists vs prose")
    assert "I love structured answers" in last_system(llm) and "Lists are the clearest" in last_user(llm)
    assert agent.selfmodel.current().source == "injected"
    agent.close()


def test_selfmodel_off_means_no_review_and_no_portrait(tmp_path, clock):
    llm = FakeLLM({"selfreview": [review()], "episode": EPISODE})
    agent = make_v2(tmp_path, clock, llm, switches=Switches.parse("lessons,intentions"))
    session(agent, clock, "One")
    assert llm.prompts("selfreview") == [] and agent.selfmodel.current() is None
    agent.close()


# ---------- intentions ----------

def test_parse_due():
    assert parse_due("2026-01-12") == "2026-01-12" and parse_due("2026-01-12T10:00") == "2026-01-12"
    assert parse_due("next week") is None and parse_due(None) is None and parse_due("2026-02-31") is None


def test_commitment_surfaces_next_session_and_closes_when_done(tmp_path, clock):
    llm = FakeLLM({"observe": [{"commitments": [{"content": "Ask how Theo's exam went", "due": None}]},
                               {"commitments": [{"content": "ask how Theo's exam went", "due": None}]},  # duplicate
                               {}, {"fulfilled": [1, 42]}],
                   "episode": EPISODE, "selfreview": {}, "chat": "Okay."})
    agent = make_v2(tmp_path, clock, llm, switches=Switches.parse("intentions"))
    agent.reply("I have an exam on Friday")
    agent.reply("Thanks")
    assert [i.content for i in agent.intentions.open()] == ["Ask how Theo's exam went"]
    assert agent.intentions.open()[0].source == "commitment"
    agent.end_session()
    clock.advance(parse_offset("3d"))
    agent.reply("Hey")
    assert "## On your mind" in last_user(llm) and "Ask how Theo's exam went" in last_user(llm)
    assert json.loads(agent.db.execute("SELECT intention_ids FROM turn_state ORDER BY message_id DESC").fetchone()[0]) == [1]
    observe_system = llm.prompts("observe")[-1]["messages"][0]["content"]
    assert "[1] Ask how Theo's exam went" in observe_system
    agent.reply("It went well!")  # the 4th observation reports it fulfilled
    assert agent.intentions.open() == [] and agent.intentions.get(1).status == "done"
    agent.close()


def test_intentions_surface_only_early_or_when_due_and_expire(tmp_path, clock):
    llm = FakeLLM({"chat": "Okay."})
    agent = make_v2(tmp_path, clock, llm, switches=Switches.parse("intentions"))
    today = clock.now().date()
    later = agent.intentions.add("Recommend a book", due=str(today + timedelta(days=5)), source="self_review")
    undated = agent.intentions.add("Ask about the sourdough", source="self_review")
    agent.reply("Hi")
    assert "Ask about the sourdough" in last_user(llm) and "Recommend a book" not in last_user(llm)
    for t in ("a", "b", "c"):
        agent.reply(t)
    assert "## On your mind" not in last_user(llm)  # past the start of the conversation
    clock.advance(parse_offset("5d"))
    agent.reply("Back")  # a new session; the dated one is due now
    assert "Recommend a book" in last_user(llm)
    clock.advance(parse_offset("31d"))
    agent.reply("Long time")
    assert agent.intentions.get(undated).status == "dropped" and agent.intentions.get(later).status == "dropped"
    agent.close()


def test_self_review_creates_and_drops_intentions_only_when_on(tmp_path, clock):
    llm = FakeLLM({"selfreview": [review(intentions=[{"content": "Send Theo the chess puzzle", "due": "2026-01-07"}]),
                                  review(drop_intentions=[1])], "episode": EPISODE})
    agent = make_v2(tmp_path, clock, llm)
    session(agent, clock, "One")
    assert "intentions" in llm.prompts("selfreview")[0]["messages"][0]["content"]
    assert agent.intentions.get(1).due == "2026-01-07" and agent.intentions.get(1).source == "self_review"
    session(agent, clock, "Two")
    assert agent.intentions.get(1).status == "dropped"
    agent.close()

    llm = FakeLLM({"selfreview": [review(intentions=[{"content": "X"}])], "episode": EPISODE})
    agent = make_v2(tmp_path / "b", clock, llm, switches=Switches.parse("selfmodel"))
    session(agent, clock, "One")
    assert "drop_intentions" not in llm.prompts("selfreview")[0]["messages"][0]["content"]
    assert agent.intentions.open() == []
    agent.close()
