"""Regression tests for the code review of the v2 branch."""

import json

import pytest

from alice.common.clock import parse_offset
from alice.v2 import chain as C
from alice.v2 import lessons as L
from alice.v2.agent import AgentV2
from alice.v2.config import V2Config

from conftest import FakeLLM, fake_embed, make_cfg


def make_v2(tmp_path, clock, llm, name="a.db", **kw):
    kw.setdefault("sync_writes", True)
    return AgentV2(make_cfg(), clock, tmp_path / name, llm=llm, embed=fake_embed, persona="P", v2=V2Config(), **kw)


def test_turn_state_goes_through_the_background_worker(tmp_path, clock):
    agent = make_v2(tmp_path, clock, FakeLLM(), sync_writes=False)
    agent.reply("Hello")
    agent.reply("Again")
    assert agent.last_reply_id() is not None  # drains the worker first
    assert agent.db.execute("SELECT COUNT(*) FROM turn_state").fetchone()[0] == 2
    agent.close()


def test_explicit_instruction_in_the_first_message_of_a_session(tmp_path, clock):
    llm = FakeLLM({"observe": {"reaction": {"signal": -0.3, "kind": "correction", "hint": "Never use bullet lists",
                                            "explicit": True, "category": "style"}}})
    agent = make_v2(tmp_path, clock, llm)
    agent.reply("From now on, no bullet lists please. What's a good tea?")
    assert [l.rule for l in agent.lessons.active()] == ["Never use bullet lists"]
    assert agent.db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 0  # no reply to react to
    agent.close()


def test_explicit_instruction_lifts_a_weakened_matching_lesson(tmp_path, clock):
    agent = make_v2(tmp_path, clock, FakeLLM())
    lid = agent.lessons.add("style", "Answer briefly", confidence=0.25)
    assert agent.lessons.add("style", "Answer briefly", confidence=L.DIRECT) == lid
    assert agent.lessons.get(lid).confidence == L.DIRECT
    agent.close()


def test_a_long_habit_over_budget_doesnt_hide_short_ones(tmp_path, clock):
    agent = make_v2(tmp_path, clock, FakeLLM())
    agent.lessons.add("style", "word " * 200, confidence=0.9)
    short = agent.lessons.add("style", "No emoji", confidence=0.7)
    assert [l.id for l in agent.lessons.habits(50)] == [short]
    agent.close()


def test_chain_with_a_missing_opinion_renders(tmp_path, clock):
    agent = make_v2(tmp_path, clock, FakeLLM())
    agent.reply("Hi")
    mid = agent.last_reply_id()
    agent.db.execute("UPDATE turn_state SET opinion_ids='[42]' WHERE message_id=?", (mid,))
    chain = agent.explain(mid)
    assert not chain["complete"] and chain["opinions"] == [] and "opinion 42 not found" in chain["missing"]
    assert "INCOMPLETE" in C.render(chain)
    agent.close()


def test_same_portrait_and_beliefs_is_not_a_new_version(tmp_path, clock):
    same = {"portrait": "I am Alice.", "beliefs": [{"text": "Honesty matters", "weight": 0.8}]}
    moved = {"portrait": "I am Alice.", "beliefs": [{"text": "Honesty matters", "weight": 0.9, "continues": 1}]}
    llm = FakeLLM({"selfreview": [same, dict(same), moved], "episode": {"summary": "x", "importance": 0.5}})
    agent = make_v2(tmp_path, clock, llm)
    for _ in range(3):
        agent.reply("Hi")
        agent.end_session()
        clock.advance(parse_offset("1d"))
    assert agent.db.execute("SELECT COUNT(*) FROM portraits").fetchone()[0] == 2  # first, then the weight change
    agent.close()


def test_intentions_keep_their_embedding(tmp_path, clock):
    calls = []
    agent = make_v2(tmp_path, clock, FakeLLM())
    agent.store.embed = lambda texts: calls.append(list(texts)) or fake_embed(texts)
    first = agent.intentions.add("Ask about the exam", source="commitment")
    agent.intentions.add("Bring up the trip", source="commitment")
    calls.clear()
    assert agent.intentions.add("ask about the exam", source="commitment") == first
    assert calls == [["ask about the exam"]]  # only the new text; open intentions are not embedded again
    agent.close()


def test_a_failing_session_close_fails_only_its_probes(tmp_path, monkeypatch):
    from alice.eval.runner import Runner
    from alice.eval.scenario import load_scenario
    path = tmp_path / "e5" / "s.yaml"
    path.parent.mkdir()
    path.write_text("id: s\nstart: 2026-01-05T10:00\nsessions:\n  - at: +0\n    turns: [hi]\n"
                    "probes:\n  - {id: a, at: +1d, ask: q}\n  - {id: b, at: +2d, ask: q, new_session: false}\n",
                    encoding="utf-8")
    runner = Runner(make_cfg(), tmp_path / "out", llm=FakeLLM(), embed=fake_embed)

    def boom(*a, **k):
        raise RuntimeError("provider down")
    monkeypatch.setattr(runner, "_closed_base", boom)
    run_dir = runner.run(load_scenario(path), "V2")
    scores = {s["probe"]: s for s in json.loads((run_dir / "scores.json").read_text())}
    assert "provider down" in scores["a"]["error"] and "reply" in scores["b"]
    assert json.loads((run_dir / "manifest.json").read_text())["status"] == "ok"
