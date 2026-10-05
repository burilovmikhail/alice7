"""Eval harness: scenario loading, runner (all conditions, probe forks, artifacts), scorers, report."""

import json
from pathlib import Path

import pytest

from alice.eval.report import build, ci95, write_report
from alice.eval.runner import Runner
from alice.eval.scenario import load_scenario
from alice.eval.scoring import check, judge, measures

from conftest import FakeLLM, fake_embed, make_cfg, user_content

REPO = Path(__file__).resolve().parents[1]

SCENARIO = """
id: test_sister
lang: ru
start: 2026-01-05T10:00
sessions:
  - at: +0
    turns:
      - user: "Привет! Меня зовут Михаил, у меня сестра Маша, она живёт в Казани."
      - user: "Ладно, пока!"
  - at: +2d
    turns:
      - "Маша переехала в Москву."
probes:
  - id: before_move
    at: +1d
    ask: "Где живёт моя сестра?"
    expect: {contains_any: ["Казан"]}
    gold_memories: ["Маша живёт в Казани"]
  - id: after_move
    at: +9d
    ask: "Где сейчас живёт моя сестра?"
    expect: {contains_any: ["Москв"], not_contains: ["Казан"]}
    judge: "States that the sister now lives in Moscow, not Kazan."
    gold_memories: ["Маша переехала в Москву"]
    measure: words
"""


def fake_llm():
    """Extraction writes what the user said; chat 'answers' by echoing the newest place found in its context."""
    def extract(kwargs):
        dialog = user_content(kwargs).split("New dialogue:")[-1]
        facts = []
        if "Казани" in dialog:
            facts.append({"content": "Сестра Михаила Маша живёт в Казани", "core": False, "entities": ["Маша"]})
        if "Москву" in dialog:
            known = user_content(kwargs).split("New dialogue:")[0]
            old = [int(line[1:line.index("]")]) for line in known.splitlines() if "Казани" in line]
            facts.append({"content": "Сестра Михаила Маша переехала в Москву", "entities": ["Маша"], "supersedes": old})
        return {"facts": facts}

    def chat(kwargs):
        text = "\n".join(str(m["content"]) for m in kwargs["messages"])
        if "Москв" in text:
            return "Твоя сестра сейчас в Москве."
        if "Казан" in text:
            return "Она живёт в Казани."
        return "Не помню, извини."

    return FakeLLM({"extract": extract, "chat": chat, "episode": {"summary": "Михаил рассказал о сестре."},
                    "carryover": lambda k: {"facts": ["Маша живёт в Москве" if "Москву" in user_content(k)
                                                      else "Маша живёт в Казани"]},
                    "judge": {"score": 0.4, "reason": "ok"}})


@pytest.fixture
def scenario(tmp_path):
    path = tmp_path / "e1" / "sister.yaml"
    path.parent.mkdir()
    path.write_text(SCENARIO, encoding="utf-8")
    return load_scenario(path)


def test_scenario_loading(scenario):
    assert scenario.id == "test_sister" and scenario.experiment == "e1" and len(scenario.sessions) == 2
    assert scenario.sessions[1].turns[0].user == "Маша переехала в Москву."
    assert [p.id for p in scenario.probes] == ["before_move", "after_move"]
    assert scenario.probes[1].judge == {"judge": "States that the sister now lives in Moscow, not Kazan."}


@pytest.mark.parametrize("condition", ["V1", "B0", "B1", "B2"])
def test_runner_end_to_end(tmp_path, scenario, condition):
    llm = fake_llm()
    runner = Runner(make_cfg(), tmp_path / "out", llm=llm, embed=fake_embed)
    run_dir = runner.run(scenario, condition, 1)

    for name in ("manifest.json", "scores.json", "summary.json", "transcript.jsonl", "agent.db",
                 "traces/llm_calls.jsonl", "traces/messages.jsonl", "probes/after_move.db"):
        assert (run_dir / name).exists(), name
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "ok" and manifest["models"]["chat"] and "api_key" not in manifest["config"]
    assert manifest["totals"]["cost"] > 0
    scores = {s["probe"]: s for s in json.loads((run_dir / "scores.json").read_text())}
    assert scores["after_move"]["judge"]["judge"]["score"] == 0.5  # snapped
    assert "measures" in scores["after_move"]

    if condition == "B0":
        assert not scores["after_move"]["passed"]  # stateless floor
    else:
        assert scores["before_move"]["passed"] and scores["after_move"]["passed"], scores
    if condition == "V1":
        assert scores["after_move"]["gold"]["recall_at_prompt"] == 1.0
        assert scores["after_move"]["context_ids"]

    # Probe isolation: probe questions never reach the main timeline
    msgs = [json.loads(line) for line in (run_dir / "traces" / "messages.jsonl").read_text().splitlines()]
    main = [m["content"] for m in msgs if m["timeline"] == "main"]
    assert not any("Где" in c for c in main)
    assert any(m["timeline"] == "probe:after_move" and "Где" in m["content"] for m in msgs)
    if condition != "B0":  # the before_move probe forked from the state before session 2: no Moscow yet
        assert "Казан" in scores["before_move"]["reply"]


def test_v1_trace_lets_you_explain_a_reply(tmp_path, scenario):
    """Acceptance 4: from traces alone, list the memories a reply saw and why each was retrieved."""
    run_dir = Runner(make_cfg(), tmp_path / "out", llm=fake_llm(), embed=fake_embed).run(scenario, "V1")
    traces = run_dir / "traces"
    messages = [json.loads(l) for l in (traces / "messages.jsonl").read_text().splitlines()]
    retrievals = [json.loads(l) for l in (traces / "retrievals.jsonl").read_text().splitlines()]
    reply = next(m for m in messages if m["timeline"] == "probe:after_move" and m["role"] == "assistant")
    question = next(m for m in messages if m["timeline"] == "probe:after_move" and m["role"] == "user")
    r = next(r for r in retrievals if r["message_id"] == question["id"] and r["purpose"] == "chat"
             and r["timeline"] == "probe:after_move")
    shown = {h["id"]: h for h in r["hits"] if h["in_prompt"]}
    assert set(reply["context_ids"]) >= set(shown)
    assert all(h["channels"] and h["score"] > 0 for h in shown.values())


def test_checks_and_measures():
    text = "Твоя сестра в Москве 🙂\n- пункт один\n- пункт два\nКак дела?"
    m = measures(text)
    assert m["bullets"] == 2 and m["emoji"] == 1 and m["questions"] == 1
    assert check(text, {"contains_any": ["москв"], "not_contains": "Казан", "max_bullets": 2, "max_emoji": 0}) == {
        "contains_any": True, "not_contains": True, "max_bullets": True, "max_emoji": False}
    with pytest.raises(ValueError):
        check(text, {"bogus": 1})


def test_judge_parses_and_snaps():
    llm = FakeLLM({"judge": {"score": "0.9", "reason": "good"}})
    assert judge(llm, "rubric", "q", "a") == {"score": 1.0, "reason": "good"}
    assert llm.prompts("judge")[0]["temperature"] == 0
    assert judge(FakeLLM({"judge": "garbage"}), "r", "q", "a")["score"] is None


def test_report(tmp_path, scenario):
    runner = Runner(make_cfg(), tmp_path / "out", llm=fake_llm(), embed=fake_embed)
    for cond in ("V1", "B0"):
        for i in (1, 2):
            runner.run(scenario, cond, i)
    text, summary = build(tmp_path / "out")
    assert "| e1 | test_sister | V1 | 2 |" in text
    assert "E4: behavioral measure vs B0" in text
    assert summary["cost"]["V1"]["runs"] == 2
    path = write_report(tmp_path / "out")
    assert path.exists() and (tmp_path / "out" / "spotcheck.csv").exists()


def test_ci95():
    mean, half = ci95([1.0, 1.0, 1.0])
    assert mean == 1.0 and half == 0.0
    assert ci95([0.5]) == (0.5, None) and ci95([]) == (None, None)


def test_repository_scenarios_load():
    paths = sorted((REPO / "experiments" / "scenarios").rglob("*.yaml"))
    by_exp: dict[str, list] = {}
    for p in paths:
        sc = load_scenario(p)
        by_exp.setdefault(sc.experiment, []).append(sc)
        assert sc.probes and sc.sessions, p
        for probe in sc.probes:
            check("", probe.expect)  # expectation keys are valid
            assert probe.at > sc.sessions[0].at
    assert set(by_exp) == {"e1", "e2", "e3", "e4"}
    assert all(len(v) >= 3 for v in by_exp.values())
    assert {sc.lang for v in by_exp.values() for sc in v} == {"ru", "en"}
    assert all(len(sc.sessions) >= 5 for sc in by_exp["e4"])


def test_estimate_runs_offline(scenario, monkeypatch):
    from alice.eval import estimate as est
    monkeypatch.setattr(est, "fetch_prices", lambda models: {m: (1e-6, 2e-6) for m in models})
    text = est.estimate([scenario], ["V1", "B0", "B1", "B2"], make_cfg(), n=5)
    assert "| V1 | 5 |" in text and "Total ≈ $" in text
