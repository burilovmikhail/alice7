"""V2 procedural memory: lesson store dynamics, self-observation, reflection, and the lessons in the prompt."""

import json

import pytest

from alice.common.clock import parse_offset
from alice.v2 import lessons as L
from alice.v2.agent import AgentV2
from alice.v2.config import V2Config
from alice.v2.lessons import LessonStore
from alice.v2.switches import Switches

from conftest import FakeLLM, fake_embed, make_cfg, user_content


@pytest.fixture
def lessons(store):
    return LessonStore(store)


def setup_v2(store):
    from alice.v2.schema import ensure_schema
    ensure_schema(store.db)


@pytest.fixture(autouse=True)
def _schema(request):
    if "store" in request.fixturenames:
        setup_v2(request.getfixturevalue("store"))


def make_v2(tmp_path, clock, llm, **kw):
    kw.setdefault("v2", V2Config())
    return AgentV2(make_cfg(), clock, tmp_path / "v2.db", llm=llm, embed=fake_embed, persona="You are Alice.",
                   sync_writes=True, **kw)


def events(lessons, lesson_id):
    return [(e["op"], round(e["confidence"], 3)) for e in lessons.history(lesson_id)]


# ---------- store ----------

def test_confidence_dynamics(lessons):
    lid = lessons.add("style", "Answer in connected prose, without lists", confidence=0.4, feedback_ids=[3, 1])
    lessons.reinforce(lid)
    assert lessons.get(lid).confidence == pytest.approx(0.4 + 0.6 * 0.35)
    for _ in range(20):
        lessons.reinforce(lid)
    assert lessons.get(lid).confidence == L.CEILING and lessons.get(lid).evidence == 22
    lessons.weaken(lid)
    assert lessons.get(lid).confidence == pytest.approx(L.CEILING * 0.6)
    for _ in range(5):
        lessons.weaken(lid)
    assert lessons.get(lid) is None and lessons.get(lid, active_only=False).status == "retired"
    history = lessons.history(lid)
    assert history[0]["op"] == "add" and json.loads(history[0]["feedback_ids"]) == [1, 3]
    assert history[-1]["op"] == "retire"


def test_near_duplicate_add_reinforces(lessons):
    a = lessons.add("style", "Answer in connected prose without lists", confidence=0.4)
    b = lessons.add("style", "Answer in connected prose without lists", confidence=0.4, message_id=9)
    assert a == b and len(lessons.active()) == 1
    assert [e["op"] for e in lessons.history(a)] == ["add", "reinforce"]
    assert lessons.history(a)[-1]["message_id"] == 9


def test_revise_keeps_confidence(lessons):
    lid = lessons.add("behavior", "Ask fewer questions", confidence=0.5)
    lessons.revise(lid, "Ask at most one question per reply", "when the user is tired")
    l = lessons.get(lid)
    assert l.rule == "Ask at most one question per reply" and l.situation == "when the user is tired"
    assert l.confidence == 0.5 and "was: Ask fewer questions" in lessons.history(lid)[-1]["note"]


def test_habits_and_situational(lessons):
    habit = lessons.add("style", "Keep replies short", confidence=0.8)
    lessons.add("style", "Use more emoji", confidence=0.4)                     # a hypothesis: not a habit
    sit = lessons.add("behavior", "Show code first, explain after", situation="questions about python code",
                      confidence=0.6)
    assert [l.id for l in lessons.habits(400)] == [habit]
    assert lessons.habits(1) == []                                            # over budget
    assert [l.id for l in lessons.situational("I have a question about my python code")] == [sit]
    assert lessons.situational("What should I cook tonight?") == []


# ---------- in the agent ----------

def observe_replies(*items):
    return {"observe": list(items) + [{}] * 20}


def test_explicit_instruction_becomes_a_habit_at_once(tmp_path, clock):
    llm = FakeLLM({**observe_replies({}, {"reaction": {"signal": -0.6, "kind": "correction", "what": "too long",
                                                       "hint": "Keep replies under 100 words", "explicit": True,
                                                       "category": "style"}}),
                   "chat": "Some reply."})
    agent = make_v2(tmp_path, clock, llm)
    agent.reply("Tell me about tyres")
    agent.reply("Please, much shorter answers from now on.")
    agent.reply("And winter tyres?")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert "## How you've learned to talk with this user" in system and "- Keep replies under 100 words" in system
    lesson = agent.lessons.active()[0]
    assert lesson.confidence == L.DIRECT and lesson.category == "style"
    user_msg = agent.db.execute("SELECT id FROM messages WHERE content LIKE 'Please, much shorter%'").fetchone()[0]
    assert agent.lessons.history(lesson.id)[0]["message_id"] == user_msg
    assert agent.lessons.history(lesson.id)[0]["llm_call_id"]
    shown = json.loads(agent.db.execute("SELECT lesson_ids FROM turn_state ORDER BY message_id DESC").fetchone()[0])
    assert shown == [lesson.id]
    assert agent.db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 0  # explicit: no feedback row
    agent.close()


def test_observer_reads_raw_replies_and_logs_feedback(tmp_path, clock):
    llm = FakeLLM({**observe_replies({"reaction": {"signal": 0.7, "kind": "praise"}},   # start: no previous reply
                                     {"reaction": {"signal": -0.5, "kind": "disengagement", "what": "the long list",
                                                   "hint": "", "explicit": False}},
                                     {"reaction": {"signal": 0.1, "kind": "neutral"}}),
                   "chat": ["- one\n- two\n- three", "Fine prose.", "More prose."]})
    agent = make_v2(tmp_path, clock, llm)
    agent.reply("What are the upsides of scooters?")
    agent.reply("ok.")
    agent.reply("Tell me more")
    prompts = llm.prompts("observe")
    assert len(prompts) == 3
    first, second = user_content(prompts[0]), user_content(prompts[1])
    assert "no previous reply" in first
    assert "- one\n- two\n- three" in second and "ok." in second
    system = prompts[1]["messages"][0]["content"].lower()
    assert not any(w in system for w in ("bullet", "list item", "length", "emoji", "word count"))  # D11
    assert prompts[0]["model"] == make_cfg().fast_model and prompts[0]["temperature"] == 0
    rows = agent.db.execute("SELECT * FROM feedback").fetchall()
    assert len(rows) == 1 and rows[0]["signal"] == -0.5 and rows[0]["what"] == "the long list"  # 0.1: noise
    first_reply = agent.db.execute("SELECT id FROM messages WHERE role='assistant' ORDER BY id").fetchone()[0]
    assert rows[0]["assistant_msg_id"] == first_reply and rows[0]["llm_call_id"]
    agent.close()


def test_replaces_only_retires_shown_lessons_and_self_decisions(tmp_path, clock):
    llm = FakeLLM({**observe_replies({}, {"replaces": [1, 999], "self": [{"rule": "I call the user Theo"}]}),
                   "chat": "Okay."})
    agent = make_v2(tmp_path, clock, llm)
    old = agent.lessons.add("style", "Address the user formally", confidence=0.7)
    agent.reply("Hi")
    agent.reply("Just call me Theo")
    assert agent.lessons.get(old) is None
    selfs = [l for l in agent.lessons.active() if l.category == "self"]
    assert [l.rule for l in selfs] == ["I call the user Theo"] and selfs[0].confidence == L.DIRECT
    agent.close()


def reflect_llm(ops_sequence, observe=None):
    return FakeLLM({"observe": observe or [], "reflect": [{"ops": ops} for ops in ops_sequence],
                    "episode": {"summary": "They talked.", "importance": 0.5}, "chat": "Okay."})


def test_reflector_operations(tmp_path, clock):
    llm = reflect_llm([[
        {"op": "add", "category": "style", "rule": "Write in prose, not lists", "confidence": 0.9, "because": [2, 77],
         "why": "dry after lists"},
        {"op": "reinforce", "id": 1, "because": [], "why": "praise"},
        {"op": "weaken", "id": 555, "why": "hallucinated id"},
        {"op": "retire", "id": 2, "why": "wrong"},
    ]])
    agent = make_v2(tmp_path, clock, llm)
    keep = agent.lessons.add("behavior", "Ask how the user is doing", confidence=0.5)
    drop = agent.lessons.add("style", "Use headers", confidence=0.5)
    agent.reply("Hi")
    sid = agent.session.id
    a, u = [r["id"] for r in agent.db.execute("SELECT id FROM messages ORDER BY id")][:2][::-1]
    f1 = agent.lessons.add_feedback(session_id=sid, assistant_msg_id=a, user_msg_id=u, signal=-0.5, kind="x",
                                    what="lists", hint="", llm_call_id=None)
    f2 = agent.lessons.add_feedback(session_id=sid, assistant_msg_id=a, user_msg_id=u, signal=0.5, kind="y",
                                    what="prose", hint="", llm_call_id=None)
    assert (keep, drop) == (1, 2) and (f1, f2) == (1, 2)
    agent.end_session()

    prompt = llm.prompts("reflect")[0]
    assert prompt["model"] == make_cfg().chat_model  # D5: the agent's own model
    assert "[1] x (-0.5): lists" in user_content(prompt) and "They talked." in user_content(prompt)
    new = [l for l in agent.lessons.active() if l.rule == "Write in prose, not lists"][0]
    assert new.confidence == L.HYPOTHESIS_MAX                     # capped: hypotheses don't start as habits
    assert json.loads(agent.lessons.history(new.id)[0]["feedback_ids"]) == [2]   # cited ids only, 77 dropped
    assert agent.lessons.get(keep).confidence > 0.5
    assert json.loads(agent.lessons.history(keep)[-1]["feedback_ids"]) == [1, 2]  # nothing cited: all consumed
    assert agent.lessons.get(drop) is None
    assert agent.lessons.unreflected() == []
    assert agent.lessons.history(keep)[-1]["llm_call_id"]
    agent.close()


def test_no_reflection_without_reactions(tmp_path, clock):
    llm = reflect_llm([[{"op": "add", "rule": "Something", "confidence": 0.5}]])
    agent = make_v2(tmp_path, clock, llm)
    agent.reply("Hi")
    agent.end_session()
    assert llm.prompts("reflect") == [] and agent.lessons.active() == []
    agent.close()


def test_mid_session_reflection_after_enough_reactions(tmp_path, clock):
    dry = {"reaction": {"signal": -0.5, "kind": "disengagement", "what": "w"}}
    llm = reflect_llm([[{"op": "add", "rule": "Write in prose", "confidence": 0.4}]], observe=[{}] + [dry] * 3)
    agent = make_v2(tmp_path, clock, llm, v2=V2Config(reflect_every=3))
    for text in ("a", "b", "c"):
        agent.reply(text)
    assert llm.prompts("reflect") == []
    agent.reply("d")  # third reaction
    assert len(llm.prompts("reflect")) == 1 and agent.lessons.unreflected() == []
    agent.close()


def test_implicit_loop_hypothesis_becomes_habit_in_a_new_session(tmp_path, clock):
    """Reactions -> reflection adds a hypothesis -> more reactions -> reinforced -> habit in the next session."""
    dry = {"reaction": {"signal": -0.5, "kind": "disengagement", "what": "the list"}}
    llm = reflect_llm([[{"op": "add", "category": "style", "rule": "Write in prose, not lists", "confidence": 0.4}],
                       [{"op": "reinforce", "id": 1}]],
                      observe=[{}, dry, {}, dry])
    agent = make_v2(tmp_path, clock, llm)
    for day in range(2):
        agent.reply("question")
        agent.reply("ok.")
        agent.end_session()
        clock.advance(parse_offset("1d"))
    agent.reply("A new topic")
    system = llm.prompts("chat")[-1]["messages"][0]["content"]
    assert "- Write in prose, not lists" in system
    assert [e["op"] for e in agent.lessons.history(1)] == ["add", "reinforce"]
    agent.close()


def test_lessons_switched_off(tmp_path, clock):
    llm = FakeLLM({"observe": {"reaction": {"signal": -1, "kind": "x", "what": "y"}}})
    agent = make_v2(tmp_path, clock, llm, switches=Switches.parse("selfmodel"))
    agent.lessons.add("style", "Keep it short", confidence=0.9)
    agent.reply("Hi")
    agent.reply("Hello?")
    assert llm.prompts("observe") == [] and "Keep it short" not in llm.prompts("chat")[-1]["messages"][0]["content"]
    agent.close()

    # with intentions on, the observer still runs, but without the lessons part and without learning
    llm = FakeLLM({"observe": {"reaction": {"signal": -1, "kind": "x", "what": "y", "hint": "h", "explicit": True}}})
    agent = make_v2(tmp_path / "b", clock, llm, switches=Switches.parse("intentions"))
    agent.reply("Hi")
    agent.reply("Hello?")
    system = llm.prompts("observe")[-1]["messages"][0]["content"]
    assert "reaction" not in system and "commitments" in system
    assert agent.lessons.active() == [] and agent.db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 0
    agent.close()
