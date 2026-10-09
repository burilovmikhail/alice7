"""V3 skeleton: switches, schedule, advance(to), and "all V3 switches off = V2"."""

import json
from datetime import datetime, time, timedelta

import pytest

from alice.common.clock import SimClock, parse_offset
from alice.v2.agent import AgentV2
from alice.v2.config import V2Config
from alice.v3 import rhythm
from alice.v3.agent import AgentV3
from alice.v3.config import V3Config
from alice.v3.switches import V3Switches

from conftest import START, FakeLLM, fake_embed, make_cfg


def scripted():
    return FakeLLM({"episode": {"summary": "They talked.", "importance": 0.5},
                    "chat": lambda k: f"Reply {len(k['messages'])}."})


def make_v3(tmp_path, clock, llm=None, name="v3.db", **kw):
    kw.setdefault("v2", V2Config())
    kw.setdefault("v3", V3Config())
    return AgentV3(make_cfg(), clock, tmp_path / name, llm=llm or scripted(), embed=fake_embed, persona="P",
                   sync_writes=True, **kw)


def requests(llm):
    return [(p, json.dumps(k["messages"], ensure_ascii=False), k.get("model")) for p, k in llm.requests]


def test_all_v3_switches_off_is_exactly_v2(tmp_path):
    c2, c3 = SimClock(START), SimClock(START)
    llm2, llm3 = scripted(), scripted()
    v2 = AgentV2(make_cfg(), c2, tmp_path / "v2.db", llm=llm2, embed=fake_embed, persona="P", sync_writes=True,
                 v2=V2Config())
    v3 = make_v3(tmp_path, c3, llm3, v3_switches=V3Switches.none())
    for agent, clock in ((v2, c2), (v3, c3)):
        agent.reply("Hi, I'm Theo.")
        clock.advance(parse_offset("5m"))
        agent.reply("What should I cook?")
        target = clock.now() + timedelta(days=2)
        if hasattr(agent, "advance"):
            assert agent.advance(target) == [] and clock.now() < target  # nothing lives in silence
        clock.set(target)
        agent.reply("Back again")
        agent.end_session()
    assert requests(llm2) == requests(llm3) and len(llm2.requests) > 4
    v2.close()
    v3.close()


def test_switch_parsing_and_probe_time_ablation(tmp_path, clock):
    assert V3Switches.parse("stream,sleep") == V3Switches(stream=True, wakes=False, sleep=True, affect=False,
                                                         initiative=False, later=False)
    with pytest.raises(ValueError):
        V3Switches.parse("stream,traits")
    agent = make_v3(tmp_path, clock)
    agent.apply_switches({"lessons": False, "sleep": False})
    assert not agent.switches.lessons and not agent.v3_switches.sleep and agent.v3_switches.stream
    with pytest.raises(ValueError):
        agent.apply_switches({"mood": False})
    assert agent.describe()["v3"]["wake_model"] == make_cfg().chat_model
    agent.close()


def test_rhythm():
    cfg = V3Config()
    day = datetime(2026, 1, 5)
    assert rhythm.awake(day.replace(hour=9), cfg) and not rhythm.awake(day.replace(hour=23, minute=30), cfg)
    assert rhythm.mode(day.replace(hour=9), cfg, False) == rhythm.IDLE
    assert rhythm.mode(day.replace(hour=1), cfg, False) == rhythm.ASLEEP
    assert rhythm.mode(day.replace(hour=9), cfg, True) == rhythm.CONVERSATION
    assert rhythm.next_sleep(day.replace(hour=1), cfg) == day.replace(hour=2)
    assert rhythm.next_sleep(day.replace(hour=2), cfg) == day.replace(hour=2) + timedelta(days=1)


def test_advance_closes_the_session_at_the_gap_and_lives_the_night(tmp_path):
    clock = SimClock(datetime(2026, 1, 5, 20, 0))
    agent = make_v3(tmp_path, clock)
    agent.reply("Evening chat")
    agent.advance(datetime(2026, 1, 6, 10, 0))
    log = agent.db.execute("SELECT at, event, ran FROM schedule_log ORDER BY id").fetchall()
    events = [(r["at"][11:16], r["event"], r["ran"]) for r in log]
    assert events[0] == ("23:00", "session_close", 1)          # 20:00 + 3 h gap, not the next message
    episode = agent.store.recent_episodes(1)[0]
    assert episode.content.startswith("Conversation on 2026-01-05 20:00")
    assert ("02:00", "sleep", 1) in events                      # something new happened: the night's sleep ran
    stream = [e[0] for e in events if e[1] == "stream"]
    # asleep: every 3 h (the 02:00 tick gives way to sleep); from 08:00 awake: hourly
    assert stream[:4] == ["05:00", "08:00", "09:00", "10:00"]
    assert agent.session is None and clock.now() <= datetime(2026, 1, 6, 10, 0)

    # the next night: nothing new, so sleep is skipped and logged as such
    agent.advance(datetime(2026, 1, 7, 3, 0))
    last_sleep = agent.db.execute("SELECT ran, note FROM schedule_log WHERE event='sleep' ORDER BY id DESC").fetchone()
    assert last_sleep["ran"] == 0 and "nothing new" in last_sleep["note"]
    # advancing again to the same time does nothing more
    n = agent.db.execute("SELECT COUNT(*) FROM schedule_log").fetchone()[0]
    agent.advance(datetime(2026, 1, 7, 3, 0))
    assert agent.db.execute("SELECT COUNT(*) FROM schedule_log").fetchone()[0] == n
    agent.close()


def test_runner_lives_through_silence_for_v3(tmp_path):
    from alice.eval.runner import Runner
    from alice.eval.scenario import load_scenario
    path = tmp_path / "e8" / "s.yaml"
    path.parent.mkdir()
    path.write_text("id: s\nstart: 2026-01-05T20:00\nsessions:\n  - at: +0\n    turns: [hi]\n"
                    "  - at: +2d\n    turns: [again]\nprobes:\n  - {id: a, at: +1d, ask: q}\n"
                    "  - {id: b, at: +1d, ask: q2}\n", encoding="utf-8")
    run_dir = Runner(make_cfg(), tmp_path / "out", llm=scripted(), embed=fake_embed).run(load_scenario(path), "V3")
    calls = [json.loads(l) for l in (run_dir / "traces" / "llm_calls.jsonl").read_text().splitlines()]
    # the probes share one base that lived the night (one episode at the 3 h gap), the main timeline its own
    assert sum(1 for c in calls if c["purpose"] == "episode" and c["timeline"].startswith("probe-base")) == 1
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "ok" and manifest["agent"]["v3_switches"]["stream"]
