"""V2 skeleton: switches, schema, context sections, turn_state, and "all switches off = V1"."""

import json

import pytest

from alice.common.clock import SimClock, parse_offset
from alice.v1.agent import AgentV1
from alice.v2.agent import AgentV2
from alice.v2.config import V2Config
from alice.v2.context import Section
from alice.v2.switches import Switches

from conftest import START, FakeLLM, fake_embed, make_cfg

FACTS = {"facts": [{"content": "Theo's sister Hannah lives in Glasgow", "core": True, "importance": 0.7,
                    "entities": ["Hannah"]}],
         "entities": [{"name": "Hannah", "type": "person", "aliases": []}],
         "relations": [{"src": "Hannah", "relation": "sister of", "dst": "USER"}]}


def scripted_llm():
    return FakeLLM({"extract": [FACTS] + [{}] * 20, "episode": {"summary": "Theo talked about his sister.",
                                                               "importance": 0.6, "entities": ["Hannah"]},
                    "chat": lambda k: f"Reply {len(k['messages'])}."})


def drive(agent, clock):
    """Two sessions with a context reset between them."""
    agent.reply("Hi, I'm Theo. My sister Hannah lives in Glasgow.")
    clock.advance(parse_offset("5m"))
    agent.reply("What should I cook tonight?")
    clock.advance(parse_offset("2d"))
    agent.reply("Any ideas for Hannah's birthday?")
    agent.end_session()


def requests(llm):
    return [(p, json.dumps(k["messages"], ensure_ascii=False), k.get("model")) for p, k in llm.requests]


def make_v2(tmp_path, clock, llm=None, name="v2.db", **kw):
    kw.setdefault("v2", V2Config())
    return AgentV2(make_cfg(), clock, tmp_path / name, llm=llm or FakeLLM(), embed=fake_embed, persona="You are Alice.",
                   sync_writes=True, **kw)


def test_all_switches_off_is_exactly_v1(tmp_path):
    """The ablation baseline: V2 with every mechanism off sends every model exactly what V1 sends."""
    c1, c2 = SimClock(START), SimClock(START)
    llm1, llm2 = scripted_llm(), scripted_llm()
    v1 = AgentV1(make_cfg(), c1, tmp_path / "v1.db", llm=llm1, embed=fake_embed, persona="You are Alice.",
                 sync_writes=True)
    v2 = make_v2(tmp_path, c2, llm2, switches=Switches.none())
    drive(v1, c1)
    drive(v2, c2)
    assert requests(llm1) == requests(llm2) and len(llm1.requests) > 5
    assert llm1.embed_calls == llm2.embed_calls
    v1.close()
    v2.close()


def test_switch_parsing():
    assert Switches.parse(None) == Switches() and Switches.parse("all") == Switches()
    assert Switches.parse("none") == Switches.none()
    assert Switches.parse("lessons, intentions") == Switches(lessons=True, selfmodel=False, intentions=True)
    assert str(Switches.parse("selfmodel")) == "selfmodel" and str(Switches.none()) == "none"
    with pytest.raises(ValueError):
        Switches.parse("lessons,affect")
    with pytest.raises(ValueError):
        Switches().with_({"mood": False})


def test_switches_persist_with_the_database_and_fork_ablation_stays_on_the_fork(tmp_path, clock):
    agent = make_v2(tmp_path, clock, switches=Switches.parse("lessons,selfmodel"))
    agent.reply("Hello")
    agent.snapshot(tmp_path / "fork.db")
    fork = AgentV2.load(tmp_path / "fork.db", make_cfg(), SimClock(clock.now()), llm=FakeLLM(), embed=fake_embed,
                        persona="You are Alice.", sync_writes=True, v2=V2Config())
    assert fork.switches == Switches(lessons=True, selfmodel=True, intentions=False)  # the run's, not the default
    fork.apply_switches({"selfmodel": False})
    fork.reply("Hi again")
    states = [json.loads(r[0]) for r in fork.db.execute("SELECT switches FROM turn_state ORDER BY message_id")]
    assert states == [{"lessons": True, "selfmodel": True, "intentions": False},
                      {"lessons": True, "selfmodel": False, "intentions": False}]
    assert agent.switches.selfmodel  # the parent is untouched
    assert agent.describe()["switches"]["selfmodel"] and agent.describe()["v2"]["reflect_model"] == make_cfg().chat_model
    fork.close()
    agent.close()


class FakeMechanism:
    def __init__(self):
        self.turns, self.sessions = [], []

    def system_section(self):
        return Section("## Who you are — in your own words", "I like short answers.",
                       framing="You wrote this about yourself.", shown={"portrait_id": 7})

    def memory_section(self, query, session):
        return Section("## In situations like this", f"- about {query[:10]}", shown={"lesson_ids": [3, 4]})

    def after_turn(self, session):
        self.turns.append(session.id)

    def after_session(self, session_id):
        self.sessions.append(session_id)


def test_sections_hooks_and_turn_state(tmp_path, clock):
    llm = FakeLLM()
    agent = make_v2(tmp_path, clock, llm)
    mech = FakeMechanism()
    agent._mechanisms["selfmodel"] = mech
    agent.reply("Tell me about tyres")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert system.startswith("You are Alice.")
    # V2 sections go after V1's parts and before the date line
    assert system.index("## You don't know anything") < system.index("## Who you are") < system.index("\n\nToday: ")
    assert "You wrote this about yourself." in system
    user = llm.prompts("chat")[-1]["messages"][-1]["content"]
    assert user.index("## Time") < user.index("## In situations like this") < user.index("</memory>")
    row = agent.db.execute("SELECT * FROM turn_state").fetchone()
    assert row["portrait_id"] == 7 and json.loads(row["lesson_ids"]) == [3, 4]
    assert agent.last_state() == {"portrait_id": 7, "lesson_ids": [3, 4]}
    assert mech.turns == [agent.session.id]
    sid = agent.session.id
    agent.end_session()
    assert mech.sessions == [sid]

    # switched off: no sections, no hooks, nothing recorded as shown
    agent.apply_switches({"selfmodel": False})
    agent.reply("And winter tyres?")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert "## Who you are" not in system and "## In situations" not in llm.prompts("chat")[-1]["messages"][-1]["content"]
    last = agent.db.execute("SELECT * FROM turn_state ORDER BY message_id DESC").fetchone()
    assert last["portrait_id"] is None and json.loads(last["lesson_ids"]) == []
    assert len(mech.turns) == 1
    agent.close()


def test_restart_finalizes_a_stale_session_after_v2_is_ready(tmp_path, clock):
    llm = FakeLLM({"episode": {"summary": "A short talk.", "importance": 0.5}})
    agent = make_v2(tmp_path, clock, llm)
    agent.reply("Hello there")
    agent.close()  # no end_session: the session stays open in the database
    clock.advance(parse_offset("5h"))
    again = make_v2(tmp_path, clock, llm)
    assert again.session is None and again.store.recent_episodes(1)
    assert again.db.execute("SELECT value FROM meta WHERE key='v2_schema_version'").fetchone()[0] == "1"
    again.close()


def test_runner_accepts_v2(tmp_path):
    from alice.eval.runner import Runner
    from alice.eval.scenario import load_scenario
    path = tmp_path / "e5" / "s.yaml"
    path.parent.mkdir()
    path.write_text("""
id: v2_smoke
start: 2026-01-05T10:00
sessions:
  - at: +0
    turns: ["Hi, I'm Theo.", "Tell me about tyres."]
probes:
  - {id: p, at: +2d, ask: "What's my name?", expect: {contains_any: ["Theo"]}}
""", encoding="utf-8")
    run_dir = Runner(make_cfg(), tmp_path / "out", llm=FakeLLM({"chat": "Theo, right?"}), embed=fake_embed).run(
        load_scenario(path), "V2")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "ok" and manifest["agent"]["switches"] == {"lessons": True, "selfmodel": True,
                                                                           "intentions": True}
    scores = json.loads((run_dir / "scores.json").read_text())
    assert scores[0]["passed"]
