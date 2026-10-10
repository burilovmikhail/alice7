"""V4: switches, "all V4 switches off = V3", the substrate living through time, turns, traces, forks."""

import json
from datetime import datetime, timedelta

import numpy as np
import pytest

from alice.common.clock import SimClock, parse_offset
from alice.v2.config import V2Config
from alice.v3.agent import AgentV3
from alice.v3.config import V3Config
from alice.v4.agent import AgentV4
from alice.v4.config import V4Config
from alice.v4.switches import V4Switches

from conftest import START, FakeLLM, fake_embed, make_cfg, user_content

EVENING = datetime(2026, 1, 5, 19, 0)   # a Monday evening


def scripted(**extra):
    return FakeLLM({"episode": {"summary": "They talked.", "importance": 0.5},
                    "chat": lambda k: f"Reply {len(k['messages'])}.", **extra})


def make_v4(tmp_path, clock, llm=None, name="v4.db", **kw):
    kw.setdefault("v2", V2Config())
    kw.setdefault("v3", V3Config())
    kw.setdefault("v4", V4Config())
    return AgentV4(make_cfg(), clock, tmp_path / name, llm=llm or scripted(), embed=fake_embed, persona="P",
                   sync_writes=True, **kw)


def requests(llm):
    return [(p, json.dumps(k["messages"], ensure_ascii=False), k.get("model")) for p, k in llm.requests]


def test_all_v4_switches_off_is_exactly_v3(tmp_path):
    c3, c4 = SimClock(EVENING), SimClock(EVENING)
    llm3, llm4 = scripted(wake={"thought": "t", "do": []}, stream="A thought."), \
        scripted(wake={"thought": "t", "do": []}, stream="A thought.")
    v3 = AgentV3(make_cfg(), c3, tmp_path / "v3.db", llm=llm3, embed=fake_embed, persona="P", sync_writes=True,
                 v2=V2Config(), v3=V3Config())
    v4 = make_v4(tmp_path, c4, llm4, v4_switches=V4Switches.none())
    for agent, clock in ((v3, c3), (v4, c4)):
        agent.reply("Hi, I'm Theo. My interview is on Thursday.")
        clock.advance(parse_offset("5m"))
        agent.reply("What should I cook?")
        target = clock.now() + timedelta(days=2)
        agent.advance(target)
        clock.set(target)
        agent.reply("Back again")
        agent.end_session()
    assert requests(llm3) == requests(llm4) and len(llm3.requests) > 10
    assert not v4.db.execute("SELECT COUNT(*) FROM v4_nodes").fetchone()[0]
    v3.close()
    v4.close()


def test_switch_parsing_and_probe_time_ablation(tmp_path, clock):
    assert V4Switches.parse("field,gate") == V4Switches(field=True, drives=False, gate=True, recall=False, traces=False,
                                                       narrative=False, sleep_mode=False, intrusions=False,
                                                       reconsolidation=False, grip=False)
    assert not V4Switches(field=False).on("gate")
    with pytest.raises(ValueError):
        V4Switches.parse("field,lessons")
    agent = make_v4(tmp_path, clock)
    agent.apply_switches({"lessons": False, "sleep": False, "narrative": False})
    assert not agent.switches.lessons and not agent.v3_switches.sleep and not agent.v4_switches.narrative
    with pytest.raises(ValueError):
        agent.apply_switches({"mood": False})
    d = agent.describe()
    assert d["v4_switches"]["field"] and len(d["v4"]["constants"]["sha256"]) == 16
    agent.close()


def test_turn_builds_nodes_and_the_context_from_the_field(tmp_path):
    clock = SimClock(EVENING)
    llm = scripted(extract=[{"facts": [{"content": "Theo has a job interview at the bank on Thursday",
                                        "importance": 0.8}]}, {}, {}])
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("Hi, I'm Theo. My interview at the bank is on Thursday.")
    f = agent.substrate.field
    assert {"user", "self"} <= set(f.kind) and "memory" in f.kind
    i = f.node_for("memory", 1)
    assert f.a[i] > 0.25 and f.salience[i] > 0          # salience sets the initial activation
    clock.advance(timedelta(minutes=2))
    agent.reply("I'm nervous about the bank interview.")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    user = user_content(llm.prompts("chat")[-1])
    assert "## How you are" in system and "## Your mood" not in system
    assert "Theo has a job interview at the bank" in user      # recalled by activation
    assert agent.db.execute("SELECT COUNT(*) FROM v4_turn_state").fetchone()[0] == 2
    assert not llm.prompts("observe") and len(llm.prompts("observe_v4")) == 2   # one cheap call per turn, no V2 one
    agent.close()


def test_reactions_become_traces_with_prediction_error(tmp_path):
    clock = SimClock(EVENING)
    reactions = [{"reaction": None}, {"reaction": {"signal": -0.6, "kind": "disengagement", "what": "the list"}},
                 {"reaction": {"signal": 0.0, "kind": "neutral", "what": ""}}]
    llm = scripted(observe_v4=reactions, chat=["- one\n- two\n- three", "Plain prose this time.", "Sure."])
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("What are the upsides of scooters?")
    clock.advance(timedelta(minutes=2))
    agent.reply("ok.")
    clock.advance(timedelta(minutes=2))
    agent.reply("And winter tyres?")
    rows = agent.db.execute("SELECT * FROM v4_traces").fetchall()
    assert len(rows) == 1 and rows[0]["kind"] == "disengagement" and rows[0]["reply"].startswith("- one\n- two")
    assert rows[0]["pe"] == pytest.approx(-0.6)       # nothing was expected yet
    pes = [json.loads(r[0]) for r in agent.db.execute("SELECT detail FROM v4_learning WHERE event='pe'")]
    assert len(pes) == 2 and pes[1]["trace"] is None   # the neutral reaction was expected: no trace
    assert agent.substrate.drives.get("frustration") > 0
    node = agent.substrate.field.node_for("trace", rows[0]["id"])
    assert agent.substrate.field.weight(node, agent.substrate.field.special("user")) >= 0.6
    agent.close()


def test_traces_are_shown_as_episodes_without_the_signal(tmp_path):
    clock = SimClock(EVENING)
    llm = scripted(observe_v4=[{"reaction": None}, {"reaction": {"signal": 0.8, "kind": "praise", "what": "prose"}},
                               {"reaction": None}])
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("Hi, I'm Mara. Tell me about Lisbon.")
    clock.advance(timedelta(minutes=2))
    agent.reply("Oh, that was lovely to read, thank you.")
    clock.advance(timedelta(days=1))
    agent.reply("What should I cook tonight?")
    user = user_content(llm.prompts("chat")[-1])
    assert "## From experience with" in user and "Tell me about Lisbon" in user and "(warmly)" in user
    assert "0.8" not in user.split("## From experience with")[1]
    agent.close()


def test_advance_lives_a_day_without_a_model_until_the_gate_fires(tmp_path):
    clock = SimClock(EVENING)
    llm = scripted(wake={"thought": "Theo is anxious about Thursday.", "about": [], "proposals": [{"type": "nothing"}]},
                   narrative={"portrait": "I am Alice.", "beliefs": [{"text": "I like prose", "weight": 0.6}]},
                   dream={"thought": "A bank made of paper."})
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("My interview at the bank is on Thursday and I'm terrified.")
    agent.advance(EVENING + timedelta(days=1, hours=2))
    db = agent.db
    assert db.execute("SELECT event FROM schedule_log WHERE event='session_close'").fetchone()
    steps = db.execute("SELECT COUNT(*) FROM v4_steps").fetchone()[0]
    assert steps >= (26 * 60 - 5) // 5                   # one row per 5 sim minutes
    modes = {r[0] for r in db.execute("SELECT DISTINCT mode FROM v4_steps")}
    assert {"conversation", "awake", "nrem", "rem"} <= modes      # it fell asleep by itself
    assert db.execute("SELECT 1 FROM v4_learning WHERE event='edges'").fetchone()
    sleep = [r[0] for r in db.execute("SELECT event FROM v4_sleep ORDER BY id")]
    assert sleep[0] == "onset" and "wake" in sleep and "narrative" in sleep
    onset = db.execute("SELECT at FROM v4_sleep WHERE event='onset'").fetchone()[0]
    assert "21:00" < onset[11:16] or onset[11:16] < "03:00"
    calls = {p for p, _ in llm.requests}
    assert "stream" not in calls                           # no periodic model call in silence (D3)
    firings = db.execute("SELECT COUNT(*) FROM wakes").fetchone()[0]
    assert firings == len(llm.prompts("wake")) <= V3Config().wakes_per_day + 1
    woke = json.loads(db.execute("SELECT detail FROM v4_sleep WHERE event='wake'").fetchone()[0])
    assert woke["reason"] == "rested" and woke["slept_hours"] > 3
    agent.close()


def test_forks_continue_identically(tmp_path):
    clock = SimClock(EVENING)
    agent = make_v4(tmp_path, clock, scripted(wake={"thought": "t", "proposals": []}))
    agent.reply("I keep thinking about the lighthouse trip.")
    agent.advance(EVENING + timedelta(hours=5))
    agent.snapshot(tmp_path / "fork.db")
    a_clock = SimClock(clock.now())
    runs = []
    for path in (tmp_path / "fork.db", tmp_path / "fork2.db"):
        if path.name == "fork2.db":
            import shutil
            shutil.copy(tmp_path / "fork.db", path)
        fork = make_v4(tmp_path, SimClock(a_clock.now()), scripted(wake={"thought": "t", "proposals": []}),
                       name=path.name)
        fork.advance(EVENING + timedelta(hours=20))
        runs.append(fork.substrate.field.a.copy())
        fork.close()
    assert np.array_equal(runs[0], runs[1])
    agent.close()


def test_manipulations_on_a_fork(tmp_path):
    clock = SimClock(EVENING)
    agent = make_v4(tmp_path, clock, scripted(
        extract=[{"facts": [{"content": "Mara loves the sea", "importance": 0.7}]}, {}],
        observe_v4=[{"reaction": None}, {"reaction": {"signal": -0.7, "kind": "frustration", "what": "length"}}],
        chat=["A very long answer.", "Ok."]))
    agent.reply("Hi, I'm Mara, I love the sea.")
    clock.advance(timedelta(minutes=2))
    agent.reply("Too long!")
    f = agent.substrate.field
    assert agent.manipulate(["reset_activations"])["applied"] and not f.a.any()
    learned_before = int((f.w0 == 0).sum())
    agent.manipulate("reset_weights")
    assert int((f.w0 == 0).sum()) == 0 and np.allclose(f.w, f.w0) and not any(f.uses)
    agent.manipulate(["remove_traces", "remove_episodic"])
    assert agent._ablated("traces") and agent._ablated("episodic")
    with pytest.raises(ValueError):
        agent.manipulate("forget_everything")
    assert learned_before >= 0
    agent.close()


def test_a_due_intention_fires_the_gate_and_writes_first(tmp_path):
    clock = SimClock(datetime(2026, 7, 20, 19, 0))   # Monday
    llm = scripted(observe_v4=[{"reaction": None, "commitments": [{"content": "Remind Clara to call the dentist",
                                                                  "due": "2026-07-23"}]}, {"reaction": None}],
                   wake=lambda k: {"thought": "Today is the dentist day.", "about": [], "proposals": [
                       {"type": "write", "content": "Morning! Today's the day to call Dr Haas."}]}
                   if "DUE NOW" in user_content(k) else {"thought": "Clara's tooth.", "proposals": []})
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("Remind me on Thursday to call the dentist, Dr Haas.")
    written = agent.advance(datetime(2026, 7, 24, 9, 0))
    assert written and written[0]["at"].startswith("2026-07-23") and "Dr Haas" in written[0]["content"]
    assert agent.db.execute("SELECT status FROM intentions_v3").fetchone()[0] == "done"
    fire = agent.db.execute("SELECT cause FROM v4_firings WHERE kind='fire' AND wake_id IS NOT NULL "
                            "ORDER BY id").fetchall()
    assert "due" in [r[0] for r in fire]
    agent.close()


def test_the_coherence_path_fires_on_a_coalition_with_two_kinds_of_urgency(tmp_path):
    clock = SimClock(datetime(2026, 1, 6, 10, 0))
    llm = scripted(wake={"thought": "The lighthouse and Clara belong together.", "about": [], "proposals": [
        {"type": "question", "content": "Why does the lighthouse matter to Clara?"},
        {"type": "write", "content": "Thinking of your lighthouse trip!"}]})
    agent = make_v4(tmp_path, clock, llm)
    s, f = agent.substrate, agent.substrate.field
    from alice.v4.field import at_minute
    vec = fake_embed(["lighthouse trip with Clara by the sea"])[0]
    nodes = [agent._node("memory", 100 + k, f"lighthouse trip with Clara by the sea {k}", vec) for k in range(3)]
    f.add_edges([(i, j, 0.9) for i in nodes for j in nodes if i < j] + [(i, f.special("user"), 0.9) for i in nodes])
    s.drives.set("social", 0.9)
    s.drives.set("curiosity", 0.9)
    s.drives.set("uncertainty", 0.5)
    events = []
    for _ in range(600):
        f.a[nodes + [f.special("user")]] = 0.9           # held up from outside, as a strong input would
        events += s.step(1.0, conversation=False)
        if any(e.kind == "fire" for e in events):
            break
    fire = next(e for e in events if e.kind == "fire")
    assert fire.reading.coherent and fire.reading.urgent and fire.cause in ("fresh", "spontaneous")
    written = []
    agent._fire(fire, written)
    # social need high and the user on its mind: the wish to speak clears the threshold (no caps, no quiet period)
    assert written and written[0]["content"] == "Thinking of your lighthouse trip!"
    speech, need, parts = agent.actions.threshold(fire)
    assert parts["unanswered"] == 1 and need >= 2.0      # now shy: the message has no answer yet
    assert agent.actions.may_speak(fire)[0] is False
    assert agent.db.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 1
    assert all(f.refractory_until[i] > s.t for i in fire.coalition) and s.gate.u == 0
    thought = f.node_for("thought", 1)
    assert thought is not None and f.own[thought] and f.weight(thought, nodes[0]) >= 0.5
    prompt = user_content(llm.prompts("wake")[0])
    assert "Right now these are on your mind at the same time" in prompt and "lighthouse" in prompt
    assert "(the user)" in prompt and at_minute(fire.t).strftime("%H:%M") in prompt
    agent.close()


def test_urgency_needs_two_kinds(tmp_path, clock):
    from alice.v4.gate import Gate
    assert not Gate.kinds_ok({"goal": 0.0, "social": 0.9, "curiosity": 0.0, "uncertainty": 0.0, "dissonance": 0.0,
                              "affect": 0.0, "fresh": 0.0})
    assert Gate.kinds_ok({"goal": 0.0, "social": 0.9, "curiosity": 0.0, "uncertainty": 0.0, "dissonance": 0.0,
                          "affect": 0.0, "fresh": 0.5})


def test_narrative_is_a_guess_written_in_sleep_and_checked_against_traces(tmp_path):
    clock = SimClock(EVENING)
    llm = scripted(
        observe_v4=[{"reaction": None}, {"reaction": {"signal": -0.7, "kind": "disengagement", "what": "the list"}},
                    {"reaction": None}],
        chat=["- a\n- b", "Fine.", "Hello."],
        narrative={"portrait": "I am Alice and I love bullet lists.",
                   "beliefs": [{"text": "I love answering in bullet lists", "weight": 0.8}]},
        dissonance={"beliefs": [{"belief": 0, "labels": [{"episode": 0, "label": "contradicts"}]}]},
        dream={"thought": "Lists falling like rain."})
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("What are the upsides of scooters, in bullet lists?")
    clock.advance(timedelta(minutes=2))
    agent.reply("ok.")
    assert not llm.prompts("selfreview")                  # no self-review at the end of the session
    agent.advance(EVENING + timedelta(days=1, hours=12))
    assert len(llm.prompts("narrative")) >= 1 and "How your replies were taken today" in \
        user_content(llm.prompts("narrative")[0])
    row = agent.db.execute("SELECT * FROM v4_dissonance").fetchone()
    assert row["share"] == 1.0 and row["value"] == pytest.approx(0.8)
    clock.set(EVENING + timedelta(days=1, hours=12))
    agent.reply("Hi again!")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert "your own guess; it may be wrong" in system and "I love bullet lists" in system
    assert "## Who you are — in your own words" not in system
    assert agent.narrator.block() and "Here is what happened" in agent.narrator.block()
    agent.close()


def test_ablations_gate_off_runs_v3_stream_and_sleep_mode_off_sleeps_at_two(tmp_path):
    clock = SimClock(EVENING)
    llm = scripted(stream="Thinking.", wake={"thought": "t", "do": []})
    agent = make_v4(tmp_path, clock, llm, v4_switches=V4Switches.parse("field,drives,recall,traces,narrative"))
    agent.reply("Hello there.")
    agent.advance(EVENING + timedelta(days=1))
    assert llm.prompts("stream")                                      # V3's stream instead of the gate
    assert agent.db.execute("SELECT 1 FROM schedule_log WHERE event='sleep' AND at LIKE '%T02:00:00'").fetchone()
    assert not agent.db.execute("SELECT COUNT(*) FROM v4_sleep").fetchone()[0]
    agent.close()


def test_minimal_drives_hold_the_rest_at_baseline(tmp_path, clock):
    agent = make_v4(tmp_path, clock, v4=V4Config(drive_set="minimal"))
    agent.reply("Hello.")
    agent.advance(clock.now() + timedelta(hours=10))
    x = agent.substrate.drives.x
    assert x["curiosity"] == 0.3 and x["boredom"] == 0.1 and x["social"] != 0.2
    agent.close()


def test_episodic_ablation_hides_episodes_and_summaries(tmp_path):
    clock = SimClock(EVENING)
    llm = scripted(episode={"summary": "They talked about the lighthouse.", "importance": 0.9})
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("Let's talk about the lighthouse.")
    agent.end_session()
    clock.advance(timedelta(days=1))
    agent.manipulate("remove_episodic")
    agent.reply("The lighthouse again?")
    user = user_content(llm.prompts("chat")[-1])
    assert "Previous conversation:" not in user and "They talked about the lighthouse" not in user
    agent.close()


def test_runner_v4_scenario_with_events_field_forks_and_model_swap(tmp_path):
    from alice.eval.runner import Runner
    from alice.eval.scenario import load_scenario
    path = tmp_path / "e13" / "s.yaml"
    path.parent.mkdir()
    path.write_text(
        "id: s\nstart: 2026-01-05T20:00\nsessions:\n  - at: +0\n    turns: [hi, more]\n"
        "  - at: +3d\n    turns: [again]\n"
        "events:\n  - {at: +1d, inject: {portrait: 'I love bullet lists.', beliefs: [{text: lists, weight: 0.9}]}}\n"
        "probes:\n  - {id: a, at: +2d, ask: q}\n  - {id: b, at: +2d, ask: q, fork: {field: [reset_activations]}}\n"
        "  - {id: c, at: +2d, ask: q, fork: {model: other/model, switches: {narrative: false}}}\n", encoding="utf-8")
    run_dir = Runner(make_cfg(), tmp_path / "out", llm=scripted(), embed=fake_embed).run(load_scenario(path), "V4")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "ok" and manifest["events"][0]["applied"]["inject"]
    scores = {r["probe"]: r for r in json.loads((run_dir / "scores.json").read_text())}
    assert scores["b"]["fork"]["applied"]["field"] == ["reset_activations"] and "error" not in scores["b"]
    assert scores["c"]["fork"]["applied"]["model"] == "other/model"
    calls = [json.loads(l) for l in (run_dir / "traces" / "llm_calls.jsonl").read_text().splitlines()]
    swapped = [c for c in calls if c["timeline"] == "probe:c" and c["purpose"] == "chat"]
    assert swapped and swapped[0]["model"] == "other/model"
    state = json.loads((run_dir / "state.json").read_text())
    assert "v4" in state and (run_dir / "field.png").exists()


def test_estimate_counts_v4_without_stream(tmp_path):
    from alice.eval.estimate import calls
    from alice.eval.scenario import load_scenario
    sc = load_scenario("experiments/scenarios/e9/reminder_day_en.yaml")
    v4 = calls(sc, "V4", make_cfg(), judge=False)
    roles = {r for r, _, _ in v4}
    assert "stream" not in roles and "wake" in roles and "reflect" in roles
    assert len(v4) < len(calls(sc, "V3", make_cfg(), judge=False))


def test_p0_pilot_runs_six_replies_from_the_same_state(tmp_path):
    from alice.v4.pilot import run_p0
    llm = scripted(chat=lambda k: "Last time you said tests are bureaucracy." if "bureaucracy" in user_content(k)
                   else "Hm.")
    out = json.loads(run_p0(make_cfg(), tmp_path, llm=llm, embed=fake_embed).read_text())
    assert len(out) == 6 and {r["state"] for r in out} == {"equal", "unequal"}
    assert all("bureaucracy" in r["memory_block"] for r in out)


def test_starting_the_chat_is_coming_to_with_a_burst_and_the_user_present(tmp_path):
    clock = SimClock(datetime(2026, 1, 5, 20, 0))
    llm = scripted(observe_v4=[{"reaction": None, "commitments": [{"content": "Ask Theo how the lighthouse trip went",
                                                                  "due": None}]}],
                   wake={"thought": "Theo is back.", "proposals": [{"type": "write", "content": "Hi Theo! Welcome back."}]})
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("I'm off to the lighthouse for the weekend.")
    agent.close()
    clock.set(datetime(2026, 1, 7, 17, 0))                       # the program was off for two days
    agent = make_v4(tmp_path, clock, llm)
    s = agent.substrate
    agent.come_to(clock.now())
    wake = json.loads(agent.db.execute("SELECT detail FROM v4_sleep WHERE event='wake' ORDER BY id DESC")
                      .fetchone()[0])
    assert wake["reason"] == "start" and wake["absent_hours"] > 40 and wake["burst"]
    assert not llm.prompts("wake")                               # absence: no thoughts in between
    intention = s.field.node_for("intention", 1)
    assert s.field.a[intention] >= 0.4 and s.gate.u >= 0.6      # unfinished business comes up first
    f = s.field
    f.add_edges([(intention, f.special("user"), 0.9)])   # (fake embeddings link little; in a real chat 0.3-0.6)
    agent.presence()
    assert s.present() and s.gate.u >= 1.2
    written = agent.advance(clock.now() + timedelta(minutes=30))
    speech = [json.loads(r[0]) for r in agent.db.execute("SELECT decisions FROM v4_firings WHERE kind='fire'")]
    assert speech, "the gate should fire soon after coming to with the user there"
    assert written == [] or written[0]["content"] == "Hi Theo! Welcome back."
    agent.close()


def test_no_hard_caps_only_the_emergency_ceiling(tmp_path, clock):
    from alice.v4 import constants as K
    from alice.v4.gate import Reading
    agent = make_v4(tmp_path, clock)
    s = agent.substrate
    s.firing_times = [s.t] * K.EMERGENCY_PER_DAY
    assert not s.ceiling_ok(Reading(), [])
    s.flush()
    assert agent.db.execute("SELECT COUNT(*) FROM v4_firings WHERE kind='ceiling'").fetchone()[0] == 1
    assert not s.ceiling_ok(Reading(), []) and s.firing_times
    s.flush()
    assert agent.db.execute("SELECT COUNT(*) FROM v4_firings WHERE kind='ceiling'").fetchone()[0] == 1   # once a day
    assert agent.initiative.blocked(clock.now()) is None          # no V3 caps or windows while the gate is on
    agent.close()


def test_grip_finds_references_into_nothing(tmp_path):
    from alice.v4.grip import assess
    clock = SimClock(EVENING)
    llm = scripted(extract=[{"facts": [{"content": "Theo's sister Clara works at a bakery", "importance": 0.7,
                                        "entities": ["Clara"]}]}, {}, {}, {}, {}, {}])
    agent = make_v4(tmp_path, clock, llm)
    agent.reply("Hi, I'm Theo. My sister Clara works at a bakery.")
    agent.end_session()
    f = agent.substrate.field
    g = lambda text, turns=0: assess(text, store=agent.store, field_=f, qv=fake_embed([text])[0], session=None,
                                     previous_turns=turns)
    assert g("So, did you think about what I told you about Munich?").kinds == ["past"]
    assert g("Did he call back?").kinds == ["pointer"]
    assert g("Did he call back?", turns=2).kinds == []                 # an antecedent can come from the conversation
    assert g("How do you think Lena will take it?").kinds == ["pointer", "name"]
    assert g("How did the interview go, by the way?").kinds == ["thing"]   # nothing remembered mentions one
    assert g("Did Clara like the bakery?").kinds == []
    assert g("How is Clara doing at the bakery?").kinds == []          # known
    assert g("What's a good way to keep bread fresh?").kinds == []     # a clear question needs nothing remembered
    assert g("Помнишь, что я говорил про Мюнхен?").kinds == ["past"]
    assert g("What should I see in Lisbon?").kinds == []               # a place, not someone it should know
    # in a reply: a section in words and uncertainty up; with the switch off, nothing
    clock.advance(timedelta(days=1))
    before = agent.substrate.drives.get("uncertainty")
    agent.reply("So, did you think about what I told you about Munich?")
    user = user_content(llm.prompts("chat")[-1])
    assert "## What you are not sure about" in user and "you don't remember anything about it" in user
    assert agent.substrate.drives.get("uncertainty") > before
    row = agent.db.execute("SELECT grip FROM v4_turn_state ORDER BY message_id DESC").fetchone()[0]
    assert "remember" in row
    agent.apply_switches({"grip": False})
    clock.advance(timedelta(days=1))
    agent.reply("Did he call back?")
    assert "## What you are not sure about" not in user_content(llm.prompts("chat")[-1])
    agent.close()


def test_grip_is_graded_a_half_match_gives_a_guess(tmp_path):
    import numpy as np
    from alice.v4 import constants as K
    from alice.v4.grip import assess
    clock = SimClock(EVENING)
    agent = make_v4(tmp_path, clock, scripted(extract=[{"facts": [
        {"content": "Theo's sister Clara keeps telling him to apply for a job at her bakery", "importance": 0.7}]}, {}]))
    agent.reply("My sister Clara keeps telling me to apply at her bakery.")
    f = agent.substrate.field
    mem = f.node_for("memory", 1)
    text = "Did you think about what I said about the job?"
    # a vector at cosine 0.54 to the memory: between the guess and the anchor thresholds
    m = f.emb[mem] / np.linalg.norm(f.emb[mem])
    q = fake_embed([text])[0]
    orth = q - (q @ m) * m
    orth /= np.linalg.norm(orth)
    v = (0.54 * m + np.sqrt(1 - 0.54 ** 2) * orth).astype(np.float32)
    assert K.GRIP_GUESS_COS <= float(f.similarities(v).max()) < K.GRIP_MEMORY_COS
    g = assess(text, store=agent.store, field_=f, qv=v, session=None, previous_turns=0)
    assert g.kinds == ["past_guess"] and "if you mean" in g.issues[0] and "bakery" in g.issues[0] and g.guessing
    far = (0.1 * m + np.sqrt(1 - 0.01) * orth).astype(np.float32)
    assert assess(text, store=agent.store, field_=f, qv=far, session=None, previous_turns=0).kinds == ["past"]
    preview = np.zeros(len(f))
    preview[mem] = 0.8
    g = assess("Should I take it?", store=agent.store, field_=f, qv=fake_embed(["Should I take it?"])[0],
               session=None, previous_turns=0, preview=preview)
    assert g.kinds == ["pointer_guess"] and "bakery" in g.issues[0] and g.value > 0.7
    agent.close()
