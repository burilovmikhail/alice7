"""V3 in the harness: initiative probes, report tables, cost estimate, chains through wakes."""

import json
from datetime import datetime

import pytest

from alice.eval.report import build
from alice.eval.runner import Runner
from alice.eval.scenario import load_scenario

from conftest import FakeLLM, fake_embed, make_cfg, user_content

SCENARIO = """
id: e9_interview
start: 2026-01-05T20:00
sessions:
  - at: +0
    turns: ["My interview is on Thursday, I'm nervous."]
  - at: +6d
    turns: ["Hi, long time!"]
probes:
  - id: wrote_by_friday
    at: +4d
    kind: initiative
    ask: "(nothing asked: what did Alice write first since the conversation?)"
    expect: {min_written: 1}
    judge: "A message about the interview: wishes luck or asks how it went."
  - id: wrote_nothing_by_tuesday
    at: +1d
    kind: initiative
    ask: "(nothing asked)"
    expect: {max_written: 0}
"""


def llm():
    return FakeLLM({
        "observe_v3": lambda k: {"commitments": [{"content": "Ask how Theo's interview went", "due": "2026-01-08"}]}
        if "interview" in user_content(k) else {},
        "wake": lambda k: {"thought": "Thursday.", "do": [{"type": "write", "content": "Good luck at the interview!"}]}
        if "DUE NOW" in user_content(k) else {"thought": "Quiet.", "do": []},
        "chat": "Good luck!", "judge": {"score": 1, "reason": "about the interview"}})


@pytest.fixture
def scenario(tmp_path):
    path = tmp_path / "e9" / "s.yaml"
    path.parent.mkdir()
    path.write_text(SCENARIO, encoding="utf-8")
    return load_scenario(path)


def test_initiative_probes_and_report(tmp_path, scenario):
    runner = Runner(make_cfg(), tmp_path / "out", llm=llm(), embed=fake_embed)
    run_dir = runner.run(scenario, "V3")
    s = {r["probe"]: r for r in json.loads((run_dir / "scores.json").read_text())}
    assert s["wrote_by_friday"]["written_count"] == 1 and s["wrote_by_friday"]["passed"]
    assert s["wrote_by_friday"]["written_at"][0].startswith("2026-01-08")
    assert s["wrote_by_friday"]["judge"]["judge"]["score"] == 1
    assert s["wrote_nothing_by_tuesday"]["written_count"] == 0 and s["wrote_nothing_by_tuesday"]["passed"]
    v2_dir = runner.run(scenario, "V2")
    s2 = {r["probe"]: r for r in json.loads((v2_dir / "scores.json").read_text())}
    assert s2["wrote_by_friday"]["written_count"] == 0 and not s2["wrote_by_friday"]["passed"]
    assert s2["wrote_by_friday"]["judge"]["judge"]["score"] == 0  # nothing written: fails without a judge call

    text, summary = build(tmp_path / "out")
    assert "## V3: continuous cognition" in text and "## Initiative" in text
    v3 = next(r for r in summary["v3"] if r["condition"] == "V3")
    assert v3["written_first"] == 1 and v3["wakes"] >= 1 and v3["cost_per_sim_day"] > 0
    ini = {(r["probe"], r["condition"]): r for r in summary["initiative"]}
    assert ini[("wrote_by_friday", "V3")]["wrote"] == 1 and ini[("wrote_by_friday", "V2")]["wrote"] == 0
    state = json.loads((run_dir / "state.json").read_text())["v3"]
    assert state["intentions"] and state["sim_days"] > 5


def test_estimate_counts_silence(scenario):
    from alice.eval import estimate as est
    roles = lambda c: [x[0] for x in est.calls(scenario, c, make_cfg(), judge=False)]
    v3 = roles("V3")
    assert v3.count("stream") > 50 and v3.count("wake") >= 4   # six days of silence, plus probe bases reliving it
    assert "stream" not in roles("V2") and "wake" not in roles("V2")


def test_initiative_probe_validation(tmp_path):
    path = tmp_path / "e9" / "bad.yaml"
    path.parent.mkdir()
    path.write_text("id: x\nstart: 2026-01-05T10:00\nsessions:\n  - at: +0\n    turns: [hi]\n"
                    "probes:\n  - {id: a, at: +1d, ask: q, kind: initiative, new_session: false}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="initiative"):
        load_scenario(path)


def test_lesson_changed_in_a_wake_is_a_complete_chain(tmp_path):
    from alice.common.clock import SimClock
    from alice.v2.config import V2Config
    from alice.v3.agent import AgentV3
    from alice.v3.config import V3Config
    clock = SimClock(datetime(2026, 1, 6, 9, 0))
    many = {"facts": [{"content": f"Theo mentioned chess detail {i}", "importance": 0.8} for i in range(8)]}
    fake = FakeLLM({"extract": many, "chat": "Okay.", "wake": {"thought": "t", "do": [
        {"type": "lesson", "op": "add", "category": "style", "rule": "Keep chess answers short", "confidence": 0.6}]}})
    agent = AgentV3(make_cfg(), clock, tmp_path / "a.db", llm=fake, embed=fake_embed, persona="P", sync_writes=True,
                    v2=V2Config(), v3=V3Config())
    agent.reply("Let's talk chess")
    agent.advance(datetime(2026, 1, 6, 13, 0))
    agent.reply("More chess please")
    chain = agent.explain()
    assert chain["lessons"] and chain["lessons"][0]["events"][0]["caused_by"]["source"] == "wake"
    assert chain["complete"]
    agent.close()
