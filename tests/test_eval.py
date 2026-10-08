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
    assert set(by_exp) == {"e1", "e2", "e3", "e4", "e5", "e6", "e7"}
    assert all(len(by_exp[e]) >= 3 for e in ("e1", "e2", "e3", "e4", "e5"))
    assert all(len(by_exp[e]) >= 2 for e in ("e6", "e7"))
    assert {sc.lang for v in by_exp.values() for sc in v} == {"en"}  # one language: no language confound
    assert all(len(sc.sessions) >= 5 for e in ("e4", "e5") for sc in by_exp[e])
    # E1-E5 each have a long scenario with key sessions among filler
    assert all(any(len(sc.sessions) >= 20 and any(s.filler for s in sc.sessions) for sc in by_exp[e])
               for e in ("e1", "e2", "e3", "e4", "e5"))
    # V2 experiments: learned behavior is shown, not stated, so their reactions are contingent on the reply
    assert all(any(t.branches for s in sc.sessions for t in s.turns) for e in ("e5", "e6") for sc in by_exp[e])
    assert any(p.fork.get("switches") for sc in by_exp["e5"] for p in sc.probes)   # E12
    assert any(p.fork.get("inject") for sc in by_exp["e5"] for p in sc.probes)     # E13
    assert any(p.kind == "self_report" for sc in by_exp["e5"] for p in sc.probes)


def test_filler_expansion(tmp_path):
    (tmp_path / "filler").mkdir()
    (tmp_path / "filler" / "en.yaml").write_text(
        "sessions:\n" + "".join(f"  - topic: t{i}\n    turns: [\"filler {i}\"]\n" for i in range(10)), encoding="utf-8")
    path = tmp_path / "scenarios" / "e1" / "long.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("""
id: long
start: 2026-01-05T19:00
sessions:
  - at: +3d
    turns: ["key fact"]
filler: {bank: en, sessions: 5, seed: 1, between: [+1d, +9d]}
probes:
  - {id: p, at: +10d, ask: "?"}
""", encoding="utf-8")
    a, b = load_scenario(path), load_scenario(path)
    assert [s.turns[0].user for s in a.sessions] == [s.turns[0].user for s in b.sessions]  # deterministic
    assert len(a.sessions) == 6 and sum(1 for s in a.sessions if s.filler) == 5
    days = [s.at.total_seconds() / 86400 for s in a.sessions]
    assert days == sorted(days) and len(set(days)) == 6 and all(d == int(d) for d in days)  # whole, distinct days


def test_gold_matching_catches_paraphrase(tmp_path, clock):
    from alice.eval.runner import gold_status
    from alice.v1.agent import AgentV1
    agent = AgentV1(make_cfg(), clock, tmp_path / "a.db", llm=FakeLLM(), embed=fake_embed, persona="P")
    mid = agent.store.add_memory("Theo prefers continuous prose rather than lists or bullet points")
    status = gold_status(agent, ["Theo asked: no lists or bullet points, prose instead"], [mid])
    assert status["items"][0]["memory_ids"] == [mid] and status["recall_at_prompt"] == 1.0
    agent.close()


def test_estimate_runs_offline(scenario, monkeypatch):
    from alice.eval import estimate as est
    monkeypatch.setattr(est, "fetch_prices", lambda models: {m: (1e-6, 2e-6) for m in models})
    text = est.estimate([scenario], ["V1", "B0", "B1", "B2"], make_cfg(), n=5)
    assert "| V1 | 5 |" in text and "Total ≈ $" in text


def test_rescore_uses_current_scenario_without_rerunning(tmp_path, scenario):
    from alice.eval.rescore import rescore_run
    run_dir = Runner(make_cfg(), tmp_path / "out", llm=fake_llm(), embed=fake_embed).run(scenario, "V1")
    agent_calls = json.loads((run_dir / "manifest.json").read_text())["totals"]["by_purpose"]["chat"]["calls"]

    # A measurement fix after the run: stricter check on one probe, a new rubric, a reworded question on another
    text = scenario.path.read_text(encoding="utf-8")
    text = text.replace('expect: {contains_any: ["Казан"]}', 'expect: {contains_any: ["Казан"], max_words: 1}')
    text = text.replace('judge: "States that the sister now lives in Moscow, not Kazan."', 'judge: "New rubric."')
    text = text.replace('ask: "Где живёт моя сестра?"', 'ask: "А где живёт сестра?"')
    scenario.path.write_text(text, encoding="utf-8")
    judge_llm = FakeLLM({"judge": {"score": 0, "reason": "new"}})

    stats = rescore_run(run_dir, make_cfg(), judge_llm=judge_llm, embed=fake_embed)
    assert stats["stale"] == ["before_move"] and stats["judge_calls"] == 1 and stats["changed"] == 1
    scores = {s["probe"]: s for s in json.loads((run_dir / "scores.json").read_text())}
    assert scores["before_move"]["stale"] and scores["after_move"]["judge"]["judge"]["score"] == 0
    assert scores["after_move"]["gold"]["recall_at_prompt"] == 1.0  # recomputed from the probe fork
    assert (run_dir / "scores.orig.json").exists()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["rescores"][0]["judge_calls"] == 1
    assert manifest["totals"]["by_purpose"]["chat"]["calls"] == agent_calls  # no agent was re-run
    text, _ = build(tmp_path / "out")
    assert "before_move" not in text  # stale probes are left out of the report

    # unchanged rubrics keep their scores on a second pass
    assert rescore_run(run_dir, make_cfg(), judge_llm=judge_llm, embed=fake_embed)["judge_calls"] == 0

    # moving a probe in time makes its saved reply stale too
    scenario.path.write_text(scenario.path.read_text(encoding="utf-8").replace("at: +9d", "at: +8d"), encoding="utf-8")
    assert rescore_run(run_dir, make_cfg(), judge_llm=judge_llm, embed=fake_embed)["stale"] == [
        "before_move", "after_move"]


CONTINGENT = """
id: test_contingent
start: 2026-01-05T10:00
sessions:
  - at: +0
    turns:
      - "Tell me about tyres."
      - user_if:
          - when: "bullets > 0"
            user: "ok."
          - when: "words >= 100 and bullets == 0"
            user: "long, but nice."
          - else: "I like the way you write."
  - at: +2d
    turns:
      - user_if:
          - {when: "bullets > 0", user: "ok."}
          - {else: "Lovely."}
probes:
  - {id: p, at: +3d, ask: "Anything else?"}
"""


def write_scenario(tmp_path, text: str, name: str = "c.yaml") -> Path:
    path = tmp_path / "e5" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_contingent_turns_choose_by_previous_reply(tmp_path):
    sc = load_scenario(write_scenario(tmp_path, CONTINGENT))
    turn = sc.sessions[0].turns[1]
    assert turn.choose("- one\n- two") == ("ok.", 0)
    assert turn.choose(" ".join(["word"] * 120)) == ("long, but nice.", 1)
    assert turn.choose("Short prose.") == ("I like the way you write.", 2)
    assert sc.sessions[0].turns[0].choose(None) == ("Tell me about tyres.", None)
    with pytest.raises(ValueError):
        turn.choose(None)


@pytest.mark.parametrize("bad", [
    'user_if: [{when: "bullets > 0", user: "a"}]',                 # no else
    'user_if: [{when: "bogus > 0", user: "a"}, {else: "b"}]',      # unknown measure
    'user_if: [{when: "bullets maybe 0", user: "a"}, {else: "b"}]',  # bad operator
])
def test_contingent_turn_validation(tmp_path, bad):
    text = f'id: x\nstart: 2026-01-05T10:00\nsessions:\n  - at: +0\n    turns:\n      - "hi"\n      - {bad}\nprobes: []\n'
    with pytest.raises(ValueError):
        load_scenario(write_scenario(tmp_path, text))


def test_first_turn_cannot_be_contingent(tmp_path):
    text = ('id: x\nstart: 2026-01-05T10:00\nsessions:\n  - at: +0\n    turns:\n'
            '      - user_if: [{when: "bullets > 0", user: "a"}, {else: "b"}]\nprobes: []\n')
    with pytest.raises(ValueError, match="first turn"):
        load_scenario(write_scenario(tmp_path, text))


def test_runner_follows_contingent_turns_and_saves_timeline(tmp_path):
    sc = load_scenario(write_scenario(tmp_path, CONTINGENT))
    replies = ["- a\n- b\n- c", "Plain prose now.", "- x\n- y", "Probe answer."]
    llm = FakeLLM({"chat": replies})
    run_dir = Runner(make_cfg(), tmp_path / "out", llm=llm, embed=fake_embed).run(sc, "B0")

    transcript = [json.loads(l) for l in (run_dir / "transcript.jsonl").read_text().splitlines()]
    assert [t["user"] for t in transcript] == ["Tell me about tyres.", "ok.", "Lovely."]
    assert [t.get("branch") for t in transcript] == [None, 0, 1]
    assert transcript[0]["measures"]["bullets"] == 3
    # the realized user text is what the agent received
    chat_users = [k["messages"][-1]["content"] for k in llm.prompts("chat")]
    assert any(c.endswith("ok.") for c in chat_users) and any(c.endswith("Lovely.") for c in chat_users)

    tl = json.loads((run_dir / "timeline.json").read_text())
    assert [s["session"] for s in tl] == [1, 2] and [s["replies"] for s in tl] == [2, 1]
    assert tl[0]["mean"]["bullets"] == 1.5 and tl[1]["mean"]["bullets"] == 2


def test_finished_runs_and_rescore_refreshes_timeline(tmp_path, scenario):
    from alice.eval.rescore import rescore_run
    from alice.eval.runner import finished_runs
    out = tmp_path / "out"
    run_dir = Runner(make_cfg(), out, llm=fake_llm(), embed=fake_embed).run(scenario, "B0", 3)
    assert finished_runs(out) == {("test_sister", "B0", 3)}

    # an unfinished run doesn't count
    broken = out / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text(json.dumps({"scenario": "test_sister", "condition": "V1", "run": 1,
                                                      "status": "running"}))
    assert finished_runs(out) == {("test_sister", "B0", 3)}

    # runs made before measures were saved get them from rescore, with no model calls for the agent
    (run_dir / "timeline.json").unlink()
    lines = [json.loads(l) for l in (run_dir / "transcript.jsonl").read_text().splitlines()]
    (run_dir / "transcript.jsonl").write_text("".join(
        json.dumps({k: v for k, v in t.items() if k != "measures"}, ensure_ascii=False) + "\n" for t in lines))
    rescore_run(run_dir, make_cfg(), judge_llm=fake_llm(), embed=fake_embed)
    assert (run_dir / "timeline.json").exists()
    assert all("measures" in json.loads(l) for l in (run_dir / "transcript.jsonl").read_text().splitlines())


def test_cli_jobs_and_skip_existing(tmp_path, scenario, monkeypatch, capsys):
    """--jobs runs in parallel threads; --skip-existing resumes."""
    import alice.cli as cli
    import alice.eval.runner as runner_mod

    real_init = runner_mod.Runner.__init__

    def fake_init(self, cfg, out_root, **kw):
        real_init(self, make_cfg(), out_root, llm=fake_llm(), embed=fake_embed, use_judge=kw.get("use_judge", True))

    monkeypatch.setattr(runner_mod.Runner, "__init__", fake_init)
    monkeypatch.setattr(cli, "_load_cfg", lambda: make_cfg())
    out = tmp_path / "out"
    cli.main(["run", str(scenario.path), "--conditions", "V1,B0,B1,B2", "--out", str(out), "--jobs", "4"])
    from alice.eval.runner import finished_runs
    assert finished_runs(out) == {("test_sister", c, 1) for c in ("V1", "B0", "B1", "B2")}

    capsys.readouterr()
    cli.main(["run", str(scenario.path), "--conditions", "V1,B0", "-n", "2", "--out", str(out), "--jobs", "2",
              "--skip-existing"])
    printed = capsys.readouterr().out
    assert "skipping 2 finished run(s)" in printed and "2 to run" in printed
    assert finished_runs(out) == {("test_sister", c, i) for c in ("V1", "B0", "B1", "B2") for i in (1,)} | {
        ("test_sister", "V1", 2), ("test_sister", "B0", 2)}


def test_run_log_keeps_only_its_own_thread(tmp_path):
    import logging
    import threading
    from alice.eval.runner import _ThreadFilter
    handler = logging.FileHandler(tmp_path / "run.log")
    handler.addFilter(_ThreadFilter())
    log = logging.getLogger("test.threads")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        log.info("mine")
        t = threading.Thread(target=lambda: log.info("other run"))
        t.start()
        t.join()
    finally:
        log.removeHandler(handler)
        handler.close()
    assert (tmp_path / "run.log").read_text().splitlines() == ["mine"]
