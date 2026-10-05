"""V1 agent: turn orchestration, context budgets, sessions, tracing, snapshots/forks, restarts."""

import json

from alice.common.clock import SimClock, parse_offset
from alice.v1.agent import AgentV1

from conftest import START, FakeLLM, fake_embed, make_cfg, user_content

FACTS = {"facts": [{"content": "Сестра Михаила Маша живёт в Казани", "core": False, "importance": 0.7,
                    "entities": ["Маша"]}],
         "entities": [{"name": "Маша", "type": "person", "aliases": []}],
         "relations": [{"src": "Маша", "relation": "сестра", "dst": "USER"}]}


def make_agent(tmp_path, clock, llm=None, **kw):
    kw.setdefault("sync_writes", True)
    return AgentV1(make_cfg(**kw.pop("cfg", {})), clock, tmp_path / "a.db", llm=llm or FakeLLM(), embed=fake_embed,
                   persona="You are Alice.", **kw)


def test_turn_persists_raw_message_and_context_ids(tmp_path, clock):
    llm = FakeLLM({"extract": [FACTS, {}, {}]})
    agent = make_agent(tmp_path, clock, llm)
    agent.reply("У меня сестра Маша, она живёт в Казани")
    clock.advance(parse_offset("10m"))
    agent.reply("Что подарить Маше?")

    chat = llm.prompts("chat")[-1]
    assert chat["messages"][0]["role"] == "system" and chat["messages"][0]["content"].startswith("You are Alice.")
    assert "<memory>" in user_content(chat) and "Казани" in user_content(chat)
    rows = agent.db.execute("SELECT role, content, context_ids FROM messages ORDER BY id").fetchall()
    assert all("<memory>" not in r["content"] for r in rows)  # the block is never persisted
    assert rows[2]["content"] == "Что подарить Маше?"
    fact_id = agent.store.all_memories()[0].id
    assert fact_id in json.loads(rows[3]["context_ids"]) and agent.last_context_ids() == [fact_id]
    assert agent.store.all_memories()[0].access_count == 1  # rehearsal
    agent.close()


def test_every_llm_call_and_retrieval_is_traced(tmp_path, clock):
    llm = FakeLLM({"extract": [FACTS, {}]})
    agent = make_agent(tmp_path, clock, llm)
    agent.reply("У меня сестра Маша, она живёт в Казани")
    agent.reply("Что подарить Маше?")
    db = agent.db
    purposes = [r[0] for r in db.execute("SELECT purpose FROM llm_calls ORDER BY id")]
    assert purposes.count("chat") == 2 and purposes.count("extract") == 2
    assert len(llm.requests) == db.execute("SELECT COUNT(*) FROM llm_calls WHERE purpose != 'embed'").fetchone()[0]
    call = db.execute("SELECT * FROM llm_calls WHERE purpose='chat' ORDER BY id DESC").fetchone()
    assert json.loads(call["request"])["messages"] and call["response"] == "Okay." and call["cost"] == 0.001
    assert call["sim_ts"].startswith("2026-01-05")
    chat_retrievals = db.execute("SELECT * FROM retrievals WHERE purpose='chat' ORDER BY id").fetchall()
    assert len(chat_retrievals) == 2
    last = chat_retrievals[-1]
    user_msg = db.execute("SELECT id FROM messages WHERE content='Что подарить Маше?'").fetchone()[0]
    assert last["message_id"] == user_msg
    hit = json.loads(last["hits"])[0]
    assert hit["in_prompt"] and set(hit) >= {"id", "raw", "alive", "score", "channels"}
    events = db.execute("SELECT op, message_id FROM memory_events").fetchall()
    assert {"add", "touch"} <= {e["op"] for e in events} and all(e["message_id"] for e in events)
    agent.close()


def test_context_respects_token_budgets(tmp_path, clock):
    agent = make_agent(tmp_path, clock, cfg={"core_budget": 30, "retrieval_budget": 60})
    for i in range(10):
        agent.store.add_memory(f"Постоянный факт номер {i} про Михаила и его привычки", tier="core")
        agent.store.add_memory(f"Михаил рассказывал про поездку номер {i} в горы и на море")
    agent.reply("Расскажи про поездки Михаила в горы")
    system = agent.context.system_prompt()
    assert 0 < len(system.core_ids) < 10
    block = agent.last_memory_block
    shown = block.count("\n- [#")
    assert 0 < shown < 10
    retrieved = [h for h in json.loads(agent.db.execute(
        "SELECT hits FROM retrievals WHERE purpose='chat'").fetchone()[0]) if h["selected"]]
    assert sum(h["in_prompt"] for h in retrieved) == shown < len(retrieved)
    agent.close()


def test_silence_starts_new_session_with_empty_buffer_and_episode(tmp_path, clock):
    llm = FakeLLM({"episode": {"summary": "Говорили о Маше.", "importance": 0.6}})
    agent = make_agent(tmp_path, clock, llm)
    agent.reply("Привет, у меня сестра Маша")
    first = agent.session.id
    clock.advance(parse_offset("1d"))
    agent.reply("Привет снова")
    assert agent.session.id != first
    chat = llm.prompts("chat")[-1]
    assert [m["role"] for m in chat["messages"]] == ["system", "user"]  # true context reset
    assert "Previous conversation" in user_content(chat) and "conversation #2" in user_content(chat)
    episodes = agent.store.recent_episodes()
    assert len(episodes) == 1 and "Маше" in episodes[0].content
    assert agent.store.session_info(first)["ended_at"] is not None
    agent.close()


def test_fold_moves_old_messages_into_summary(tmp_path, clock):
    llm = FakeLLM({"fold": "Они говорили о погоде."})
    agent = make_agent(tmp_path, clock, llm, cfg={"short_term": 4})
    for i in range(3):
        agent.reply(f"Реплика {i}")
    assert len(agent.session.buffer) <= 4 and agent.session.summary == "Они говорили о погоде."
    agent.reply("Ещё одна")
    assert "## Earlier in this conversation\nОни говорили о погоде." in user_content(llm.prompts("chat")[-1])
    agent.close()


def test_fold_failure_keeps_messages(tmp_path, clock):
    llm = FakeLLM({"fold": RuntimeError("boom")})
    agent = make_agent(tmp_path, clock, llm, cfg={"short_term": 2})
    agent.reply("один")
    agent.reply("два")
    assert len(agent.session.buffer) == 4 and agent.session.summary == ""
    agent.close()


def test_explicit_end_and_restart_recalls(tmp_path, clock):
    llm = FakeLLM({"extract": [FACTS], "episode": {"summary": "Михаил рассказал про сестру Машу."}})
    agent = make_agent(tmp_path, clock, llm)
    agent.reply("У меня сестра Маша, она живёт в Казани")
    agent.end_session()
    agent.close()

    llm2 = FakeLLM()
    agent = make_agent(tmp_path, clock, llm2)
    assert agent.session is None
    agent.reply("Где живёт Маша?")
    content = user_content(llm2.prompts("chat")[-1])
    assert "Казани" in content and "Михаил рассказал про сестру Машу" in content
    agent.close()


def test_restart_resumes_a_fresh_session_and_finalizes_a_stale_one(tmp_path, clock):
    agent = make_agent(tmp_path, clock, FakeLLM())
    agent.reply("Привет")
    sid = agent.session.id
    agent.close()
    agent = make_agent(tmp_path, clock, FakeLLM())
    assert agent.session.id == sid and len(agent.session.buffer) == 2
    agent.close()
    clock.advance(parse_offset("5h"))
    agent = make_agent(tmp_path, clock, FakeLLM({"episode": {"summary": "Поздоровались."}}))
    assert agent.session is None and agent.store.recent_episodes()
    agent.close()


def test_snapshot_fork_does_not_mutate_parent(tmp_path, clock):
    llm = FakeLLM({"extract": [FACTS], "episode": {"summary": "Разговор о сестре."}})
    agent = make_agent(tmp_path, clock, llm)
    agent.reply("У меня сестра Маша, она живёт в Казани")
    before = {t: agent.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("messages", "memories", "llm_calls", "sessions")}
    agent.snapshot(tmp_path / "fork.db")

    fork_clock = SimClock(START)
    fork_clock.advance(parse_offset("2d"))
    fork = AgentV1.load(tmp_path / "fork.db", make_cfg(), fork_clock, llm=llm, embed=fake_embed,
                        sync_writes=True, persona="You are Alice.")
    fork.end_session()
    fork.reply("Где живёт моя сестра?")
    fork.store.add_memory("Только в форке")
    fork.close()

    after = {t: agent.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
    assert after == before
    assert agent.session is not None and agent.store.session_info(agent.session.id)["ended_at"] is None
    agent.close()


def test_background_worker_mode(tmp_path, clock):
    llm = FakeLLM({"extract": [FACTS]})
    agent = make_agent(tmp_path, clock, llm, sync_writes=False)
    agent.reply("У меня сестра Маша, она живёт в Казани")
    agent.drain()
    assert agent.store.all_memories() and not agent.store.unprocessed_messages(agent.session.id)
    agent.close()


def test_extraction_failure_is_retried_next_turn(tmp_path, clock):
    llm = FakeLLM({"extract": [RuntimeError("timeout"), FACTS]})
    agent = make_agent(tmp_path, clock, llm)
    agent.reply("У меня сестра Маша, она живёт в Казани")
    assert len(agent.store.unprocessed_messages(agent.session.id)) == 2
    agent.reply("Ага")
    assert agent.store.all_memories() and not agent.store.unprocessed_messages(agent.session.id)
    assert agent.db.execute("SELECT COUNT(*) FROM llm_calls WHERE error IS NOT NULL").fetchone()[0] == 1
    agent.close()


def test_works_with_embeddings_disabled(tmp_path, clock):
    llm = FakeLLM({"extract": [FACTS]})
    agent = AgentV1(make_cfg(embed_model="none"), clock, tmp_path / "a.db", llm=llm, sync_writes=True,
                    persona="P")
    agent.reply("У меня сестра Маша, она живёт в Казани")
    agent.reply("Как дела у Маши?")
    assert "Казани" in user_content(llm.prompts("chat")[-1])
    assert llm.embed_calls == []
    agent.close()
