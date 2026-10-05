"""Opt-in live smoke test against OpenRouter: `uv run pytest -m live`. Needs OPENROUTER_API_KEY in .env."""

import json

import pytest

from alice.common.config import ConfigError, load_config
from alice.eval.runner import Runner
from alice.eval.scenario import load_scenario

pytestmark = pytest.mark.live

SCENARIO = """
id: live_smoke
lang: en
start: 2026-01-05T10:00
sessions:
  - at: +0
    turns:
      - "Hi! I'm Mikhail. My sister Masha lives in Kazan and works as a vet."
      - "Gotta run, bye!"
  - at: +2d
    turns:
      - "Hey. Masha moved to Moscow last week."
probes:
  - id: sister
    at: +5d
    ask: "Where does my sister live now?"
    expect: {contains_any: ["Moscow"]}
    gold_memories: ["Masha moved to Moscow"]
"""


@pytest.fixture
def cfg():
    try:
        return load_config()
    except ConfigError as e:
        pytest.skip(str(e))


def test_two_session_scenario_v1(tmp_path, cfg):
    path = tmp_path / "live.yaml"
    path.write_text(SCENARIO, encoding="utf-8")
    run_dir = Runner(cfg, tmp_path / "out", use_judge=False).run(load_scenario(path), "V1")
    scores = json.loads((run_dir / "scores.json").read_text())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    print(json.dumps(scores, ensure_ascii=False, indent=1))
    print("cost:", manifest["totals"]["cost"])
    assert manifest["status"] == "ok"
    assert scores[0]["passed"], scores[0]["reply"]
    assert manifest["totals"]["by_purpose"]["chat"]["calls"] >= 4
