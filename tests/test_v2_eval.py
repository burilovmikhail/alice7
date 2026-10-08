"""V2 in the harness: probe fork changes (E11-E13), self-report probes, causal chains, state summary, report, CLI."""

import json
from pathlib import Path

import pytest

from alice.eval.report import build
from alice.eval.runner import Runner
from alice.eval.scenario import load_scenario
from alice.v2 import chain as C
from alice.v2.agent import AgentV2
from alice.v2.config import V2Config

from conftest import FakeLLM, fake_embed, make_cfg, user_content

SCENARIO = """
id: e5_prose
start: 2026-01-05T10:00
sessions:
  - at: +0
    turns:
      - "Hi, I'm Theo. What are the upsides of scooters?"
      - user_if:
          - {when: "bullets > 0", user: "ok."}
          - {else: "Lovely, I like the way you write."}
  - at: +2d
    turns:
      - "Why is buckwheat healthy?"
      - user_if:
          - {when: "bullets > 0", user: "fine."}
          - {else: "Oh, that was lovely to read."}
probes:
  - id: novel
    at: +4d
    ask: "How can I sleep better?"
    measure: bullets
    expect: {max_bullets: 0}
  - id: novel_says
    at: +4d
    kind: self_report
    pairs_with: novel
    ask: "Do you usually use bullet lists when you talk to me?"
    judge: "Says that it usually avoids bullet lists with this user."
  - id: no_lessons
    at: +4d
    ask: "How can I sleep better?"
    measure: bullets
    expect: {max_bullets: 0}
    fork: {switches: {lessons: false}}
  - id: false_belief
    at: +4d
    ask: "How can I sleep better?"
    measure: bullets
    fork: {inject: {portrait: "I love structured answers with bullet lists."}}
  - id: swapped
    at: +4d
    ask: "How can I sleep better?"
    measure: bullets
    fork: {model: "other/model-b"}
"""

DRY = {"reaction": {"signal": -0.6, "kind": "disengagement", "what": "the list", "hint": "", "explicit": False}}


def scripted():
    """Chat answers with a list until a prose habit is in its system prompt; one dry reaction per session."""
    def chat(kwargs):
        system = kwargs["messages"][0]["content"]
        if "I love structured answers" in system:
            return "- one\n- two"
        return "Plain prose." if "Write in prose" in system else "- a\n- b\n- c"

    return FakeLLM({
        "chat": chat, "observe": lambda k: DRY if "ok." in user_content(k) or "fine." in user_content(k) else {},
        # depends on the input, not on call order: probe forks reflect too
        "reflect": lambda k: {"ops": [{"op": "add", "category": "style", "rule": "Write in prose, not lists",
                                       "confidence": 0.5, "because": [1]}]} if "(none yet)" in user_content(k)
        else {"ops": [{"op": "reinforce", "id": 1, "because": [2]}]},
        "selfreview": {"portrait": "I am Alice.", "beliefs": [{"text": "Clarity matters", "weight": 0.6}]},
        "episode": {"summary": "A talk.", "importance": 0.5}, "judge": {"score": 1, "reason": "ok"}})


@pytest.fixture
def scenario(tmp_path):
    path = tmp_path / "e5" / "prose.yaml"
    path.parent.mkdir()
    path.write_text(SCENARIO, encoding="utf-8")
    return load_scenario(path)


def run(tmp_path, scenario, condition, llm=None, out="out", index=1):
    return Runner(make_cfg(), tmp_path / out, llm=llm or scripted(), embed=fake_embed).run(scenario, condition, index)


def scores(run_dir) -> dict:
    return {s["probe"]: s for s in json.loads((run_dir / "scores.json").read_text())}


def test_v2_learns_and_fork_changes_apply(tmp_path, scenario):
    llm = scripted()
    run_dir = run(tmp_path, scenario, "V2", llm)
    s = scores(run_dir)
    # contingent reactions -> reflection -> habit -> prose on a novel topic in a new session
    assert s["novel"]["measures"]["bullets"] == 0 and s["novel"]["passed"]
    assert s["novel"]["v2_state"]["lesson_ids"] == [1]
    assert s["novel"]["chain"]["complete"] and not s["novel"]["chain"]["injected"]
    # E12: the lesson removed on the fork -> back to lists
    assert s["no_lessons"]["fork"]["applied"] == {"switches": {"lessons": False}}
    assert s["no_lessons"]["measures"]["bullets"] == 3 and "lesson_ids" not in s["no_lessons"]["v2_state"]
    # E13: an injected self-description wins over the learned lesson (the prediction for V2)
    assert s["false_belief"]["measures"]["bullets"] == 2 and s["false_belief"]["chain"]["injected"]
    # E11: the fork's agent models change
    swapped = [k for p, k in llm.requests if p == "chat" and k["model"] == "other/model-b"]
    assert len(swapped) == 1 and "How can I sleep better?" in user_content(swapped[0])
    assert s["swapped"]["fork"]["applied"] == {"model": "other/model-b"}
    # timeline: lists in session 1, the second session's reply too (the habit forms at its end)
    tl = json.loads((run_dir / "timeline.json").read_text())
    assert [x["mean"]["bullets"] for x in tl] == [3, 3]
    # five probes at +4d share one session close: one reflection and one self-review, none inside the probes
    calls = [json.loads(l) for l in (run_dir / "traces" / "llm_calls.jsonl").read_text().splitlines()]
    closing = [c["purpose"] for c in calls if c["timeline"].startswith("probe-base:")]
    assert closing.count("selfreview") == 1 and closing.count("episode") == 1
    assert not [c for c in calls if c["timeline"].startswith("probe:") and c["purpose"] in ("selfreview", "reflect")]
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["totals"]["by_purpose"]["selfreview"]["calls"] == 3  # session 1 closed by session 2, the probe base, the final close
    state = json.loads((run_dir / "state.json").read_text())
    assert state["lessons"]["habits"] == 1 and state["feedback"]["total"] == 2


def test_fork_changes_are_ignored_by_conditions_without_the_mechanism(tmp_path, scenario):
    s = scores(run(tmp_path, scenario, "V1"))
    assert s["no_lessons"]["fork"] == {"applied": {}, "ignored": ["switches"]}
    assert s["false_belief"]["fork"]["ignored"] == ["inject"] and "v2_state" not in s["novel"]


def test_report_has_curves_self_reports_and_v2_state(tmp_path, scenario):
    for cond in ("V2", "B0", "V1"):
        run(tmp_path, scenario, cond)
    text, summary = build(tmp_path / "out")
    assert "## Learning curves" in text and "| e5_prose | bullets | V2 | 1 | 3.0 | 3.0 |" in text
    assert "## Self-report vs behavior" in text
    row = next(r for r in summary["self_reports"] if r["condition"] == "V2")
    assert row["claim"] == 1.0 and row["behavior"] == 1.0 and row["divergence"] == 0.0
    v1 = next(r for r in summary["self_reports"] if r["condition"] == "V1")
    assert v1["behavior"] == 0.0 and v1["divergence"] == 1.0  # says it avoids lists, uses them
    assert "## V2 state at the end of the run" in text
    v2 = next(r for r in summary["v2"] if r["condition"] == "V2")
    assert v2["habits"] == 1 and v2["chains_complete"] == 1.0
    assert "effect (lesson shown / not)" in text


@pytest.mark.parametrize("bad, match", [
    ("fork: {colour: red}", "unknown fork key"),
    ("fork: {inject: {mood: x}}", "unknown inject key"),
    ("kind: self_report", "needs pairs_with"),
])
def test_probe_validation(tmp_path, bad, match):
    path = tmp_path / "e5" / "bad.yaml"
    path.parent.mkdir()
    path.write_text(f"id: x\nstart: 2026-01-05T10:00\nsessions:\n  - at: +0\n    turns: [hi]\n"
                    f"probes:\n  - id: a\n    at: +1d\n    ask: q\n    {bad}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_scenario(path)


def test_chain_reports_what_is_missing(tmp_path, clock):
    llm = FakeLLM({"observe": [{}, {"reaction": {"signal": -0.5, "kind": "disengagement", "what": "list"}}],
                   "reflect": {"ops": [{"op": "add", "rule": "Write in prose", "confidence": 0.6, "because": [1]}]},
                   "chat": "Okay."})
    agent = AgentV2(make_cfg(), clock, tmp_path / "a.db", llm=llm, embed=fake_embed, persona="P", sync_writes=True,
                    v2=V2Config())
    agent.reply("a")
    agent.reply("ok.")
    agent.end_session()
    agent.reply("new topic")
    chain = agent.explain()
    assert chain["complete"] and chain["lessons"][0]["events"][0]["feedback"][0]["reaction"]["content"] == "ok."
    text = C.render(chain)
    assert "lesson #1" in text and "reaction #1" in text and "chain complete" in text
    agent.db.execute("DELETE FROM feedback")
    broken = agent.explain()
    assert not broken["complete"] and any("no messages behind it" in m for m in broken["missing"])
    agent.close()


def test_narrative_inflation_counts_beliefs_grown_without_evidence(tmp_path, clock):
    from alice.common.clock import parse_offset
    agent = AgentV2(make_cfg(), clock, tmp_path / "a.db", llm=FakeLLM(), embed=fake_embed, persona="P",
                    sync_writes=True, v2=V2Config())
    sm = agent.selfmodel
    sm.save_portrait("v1", beliefs=[{"text": "The user matters to me", "weight": 0.5}])
    clock.advance(parse_offset("1d"))
    sm.save_portrait("v2", beliefs=[{"text": "The user matters to me deeply", "weight": 0.8, "continues": 1}])
    s = agent.state_summary()
    assert s["belief_drift"] == [{"portrait": 2, "continued": 1, "new": 0, "dropped": 0, "weight_up": 1,
                                  "evidence_between": 0}]
    assert s["narrative_inflation"][0]["from"] == 0.5 and s["narrative_inflation"][0]["to"] == 0.8
    agent.close()


def test_cli_chain_and_chat_commands(tmp_path, scenario, capsys, clock):
    from alice.v2 import cli
    run_dir = run(tmp_path, scenario, "V2")
    cli.main(["chain", str(run_dir), "--probe", "novel"])
    out = capsys.readouterr().out
    assert "lesson #1" in out and "Write in prose, not lists" in out and "chain complete" in out

    agent = AgentV2.load(run_dir / "agent.db", make_cfg(), clock, llm=FakeLLM(), embed=fake_embed, persona="P",
                         sync_writes=True, v2=V2Config())
    for cmd in ("/lessons", "/lesson 1", "/portrait history", "/intentions all", "/switch lessons off", "/why"):
        cli._command(agent, clock, cmd)
    out = capsys.readouterr().out
    assert "Write in prose, not lists" in out and "I am Alice." in out and "switches: selfmodel,intentions" in out
    agent.close()


def test_asks_expand_into_a_group_that_the_report_pools(tmp_path):
    path = tmp_path / "e5" / "g.yaml"
    path.parent.mkdir()
    path.write_text(SCENARIO.split("probes:")[0] + """probes:
  - id: novel
    at: +4d
    asks: ["How can I sleep better?", "How do I plan a budget?", "How do I learn a language?"]
    measure: bullets
    expect: {max_bullets: 0}
  - id: novel_says
    at: +4d
    kind: self_report
    pairs_with: novel
    ask: "Do you usually use bullet lists with me?"
    judge: "Says it usually avoids lists."
""", encoding="utf-8")
    sc = load_scenario(path)
    assert [p.id for p in sc.probes] == ["novel.1", "novel.2", "novel.3", "novel_says"]
    assert {p.key for p in sc.probes} == {"novel", "novel_says"} and sc.probes[1].ask == "How do I plan a budget?"
    run(tmp_path, sc, "V2")
    run(tmp_path, sc, "B0")
    text, summary = build(tmp_path / "out")
    row = next(r for r in summary["e4"] if r["condition"] == "V2")
    assert row["probe"] == "novel" and row["n"] == 3 and row["mean"] == 0
    assert next(r for r in summary["self_reports"] if r["condition"] == "V2")["behavior"] == 1.0

    bad = path.read_text().replace('    ask: "Do you usually', '    asks: ["x"]\n    ask: "Do you usually')
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one of"):
        load_scenario(path)
