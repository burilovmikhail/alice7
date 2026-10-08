"""B3 reflective carry-over: B2 + notes on how the assistant talks, written by the reflect model."""

import json

from alice.baselines.b3 import ReflectiveCarryOverAgent
from alice.common.clock import parse_offset

from conftest import FakeLLM, make_cfg, user_content


def test_b3_keeps_how_i_talk_notes_with_the_reflect_model(tmp_path, clock, monkeypatch):
    notes = {"facts": ["The user is Theo"], "conversations": [], "how_i_talk": ["I answer in prose, without lists"]}
    llm = FakeLLM({"carryover": notes, "chat": "Okay."})
    agent = ReflectiveCarryOverAgent(make_cfg(), clock, tmp_path / "b3.db", llm=llm, persona="You are Alice.")
    agent.reply("Hi, I'm Theo. Upsides of scooters?")
    agent.reply("ok.")
    agent.end_session()
    call = llm.prompts("carryover")[0]
    assert call["model"] == make_cfg().chat_model                 # D9: the model V2 reflects with
    assert "how_i_talk" in call["messages"][0]["content"] and "User: ok." in user_content(call)
    clock.advance(parse_offset("1d"))
    agent.reply("New topic")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert "I answer in prose, without lists" in system
    assert agent.describe() == {"notes_model": make_cfg().chat_model}
    agent.close()

    monkeypatch.setenv("ALICE_REFLECT_MODEL", "some/other-model")
    agent = ReflectiveCarryOverAgent(make_cfg(), clock, tmp_path / "b3b.db", llm=llm, persona="P")
    assert agent.notes_model == "some/other-model"
    agent.close()


def test_estimate_counts_v2_and_b3_calls(tmp_path, monkeypatch):
    from alice.eval import estimate as est
    from alice.eval.scenario import load_scenario
    path = tmp_path / "e5" / "s.yaml"
    path.parent.mkdir()
    path.write_text("id: s\nstart: 2026-01-05T10:00\nsessions:\n  - at: +0\n    turns: [a, b]\n"
                    "  - at: +1d\n    turns: [c]\nprobes:\n  - {id: p, at: +2d, ask: q}\n", encoding="utf-8")
    sc = load_scenario(path)
    roles = lambda cond: [c[0] for c in est.calls(sc, cond, make_cfg(), judge=False)]
    assert roles("V2").count("observe") == 3 and roles("V2").count("reflect") == 2 * 2 + 2  # sessions + probe fork
    assert "observe" not in roles("V1") and "reflect" not in roles("V1")
    assert roles("B3").count("reflect") == 3 and roles("B2").count("reflect") == 0
