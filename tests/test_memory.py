"""Memory subsystem: store, extractor, session/episodes, retrieval, time parsing (ported from Alice7 test_memory)."""

from datetime import date, timedelta

import pytest

from alice.common.clock import parse_offset
from alice.common.config import Config
from alice.common.db import connect
from alice.common.llm import as_int, as_list
from alice.common.trace import Tracer
from alice.common.timeparse import parse_time_range
from alice.v1.context import ContextBuilder
from alice.v1.extractor import Extractor
from alice.v1.retrieval import retention, search
from alice.v1.session import Session, finalize_session
from alice.v1.store import MemoryStore

from conftest import FakeLLM, fake_embed, make_cfg


def hits(store, query, clock, **kw):
    return search(store, query, now=clock.now(), **kw).hits


def test_extractor_writes_core_facts_entities_and_relations(store, clock):
    sid = store.start_session()
    store.add_message(sid, "user", "Привет, меня зовут Михаил, у меня сестра Маша")
    store.add_message(sid, "assistant", "Приятно познакомиться!")
    llm = FakeLLM({"extract": {
        "facts": [
            {"content": "Пользователя зовут Михаил", "core": True, "importance": 0.9, "entities": ["USER"]},
            {"content": "У Михаила есть сестра Маша", "core": True, "importance": 0.7, "entities": ["Маша"]},
        ],
        "entities": [{"name": "Маша", "type": "person", "aliases": ["Мария"]},
                     {"name": "USER", "type": "person", "aliases": ["Михаил"]}],
        "relations": [{"src": "Маша", "relation": "сестра", "dst": "USER"}],
    }}).bind(store.tracer)
    Extractor(store, llm, clock).process_pending(sid)

    assert [m.content for m in store.core_memories()] == ["Пользователя зовут Михаил", "У Михаила есть сестра Маша"]
    assert store.unprocessed_messages(sid) == []
    assert store.find_entity("Мария").name == "Маша"
    assert store.find_entity("Михаил").id == store.user_id
    assert store.user_name() == "Михаил"
    system = ContextBuilder(store, make_cfg(), clock, "PERSONA").system_prompt()
    assert "Пользователя зовут Михаил" in system.text and system.text.startswith("PERSONA")
    assert "2026-01-05, Monday" in system.text


def test_extractor_ignores_hallucinated_ids(store, clock):
    shown = store.add_memory("Михаил живёт в Казани")
    hidden = store.add_memory("Совсем другая тема про погоду на Марсе")
    for _ in range(10):  # push `hidden` out of "recent 8" and make sure search won't surface it
        store.add_memory(f"Ничего не значащая запись номер {_} про чай")
    sid = store.start_session()
    store.add_message(sid, "user", "Я переехал из Казани в Москву")
    data = {"facts": [{"content": "Михаил переехал в Москву", "supersedes": [shown, hidden, 9999],
                       "because": ["#9999", hidden]}]}
    Extractor(store, FakeLLM({"extract": data}).bind(store.tracer), clock).process_pending(sid)

    active = {m.id for m in store.all_memories()}
    assert shown not in active and hidden in active
    assert not store.db.execute("SELECT 1 FROM memory_links WHERE src=?", (hidden,)).fetchone()


def test_extractor_tolerates_format_slips(store, clock):
    sid = store.start_session()
    store.add_message(sid, "user", "Кота зовут Барсик")
    data = {"facts": {"content": "Кота Михаила зовут Барсик", "entities": "Барсик", "supersedes": 7},
            "entities": "мусор", "relations": [{"src": "Барсик"}]}
    Extractor(store, FakeLLM({"extract": data}).bind(store.tracer), clock).process_pending(sid)
    assert [m.content for m in store.all_memories()] == ["Кота Михаила зовут Барсик"]


def test_search_by_inflected_name_and_relations(store, clock):
    store.upsert_entity("USER", "person", ["Михаил"])
    store.link_entities("Маша", "сестра", "USER")
    store.add_memory("Маша любит кататься на лошадях", entities=["Маша"])
    store.add_memory("Михаил работает программистом")

    found = hits(store, "что подарить Маше?", clock)
    assert found and found[0].memory.content.startswith("Маша любит")
    assert found[0].channels["entity"] > 0

    session = Session.start(store, FakeLLM(), make_cfg())
    block = ContextBuilder(store, make_cfg(), clock, "P").memory_block("что подарить Маше?", session)
    assert "лошадях" in block.text and "Маша — сестра — the user (Михаил)" in block.text


def test_duplicate_is_not_stored_twice(store):
    a = store.add_memory("Михаил живёт в Казани")
    b = store.add_memory("Михаил живёт в Казани", tier="core")
    assert a == b
    assert store.core_memories()[0].id == a  # promoted to core by the duplicate
    ops = [r[0] for r in store.db.execute("SELECT op FROM memory_events ORDER BY id")]
    assert ops == ["add", "dedup"]


def test_supersede_hides_old_fact_but_keeps_history(store, clock):
    old = store.add_memory("Михаил живёт в Казани")
    new = store.add_memory("Михаил переехал в Москву")
    store.supersede(old, new)
    found = [h.memory.id for h in hits(store, "где живёт Михаил", clock, min_score=0)]
    assert old not in found and new in found
    row = store.db.execute("SELECT superseded_by, valid_to FROM memories WHERE id=?", (old,)).fetchone()
    assert row[0] == new and row[1] is not None


def test_finalize_creates_episode_linked_to_facts(store, clock):
    sid = store.start_session()
    store.add_message(sid, "user", "Вчера ходил в поход на Эльбрус")
    earlier = store.add_memory("Conversation on 2026-01-01 10:00: говорили о подготовке к походу", kind="episode",
                               valid_from="2026-01-01T10:00:00")
    fact = store.add_memory("Михаил ходил в поход на Эльбрус", source_session=sid)
    llm = FakeLLM({"episode": {"summary": "Обсуждали поход на Эльбрус.", "importance": 0.6,
                               "entities": ["Эльбрус"], "continues": [earlier, 4242]}}).bind(store.tracer)
    episode_id = finalize_session(store, llm, clock, sid)

    episode = store.memories_by_ids([episode_id])[episode_id]
    assert episode.kind == "episode" and "Эльбрус" in episode.content
    assert episode.valid_from == store.session_info(sid)["started_at"]
    links = set(store.db.execute("SELECT src, dst, relation FROM memory_links").fetchall())
    assert (episode_id, fact, "contains") in {tuple(r) for r in links}
    assert (earlier, episode_id, "led_to") in {tuple(r) for r in links}
    assert store.open_sessions() == []


def test_finalize_survives_format_slips(store, clock):
    sid = store.start_session()
    store.add_message(sid, "user", "Поговорили о книгах")
    llm = FakeLLM({"episode": {"summary": "Поговорили о книгах.", "entities": "книги", "continues": 7}})
    finalize_session(store, llm.bind(store.tracer), clock, sid)
    assert store.open_sessions() == []
    assert store.db.execute("SELECT COUNT(*) FROM memories WHERE kind='episode'").fetchone()[0] == 1


def test_empty_session_is_deleted(store, clock):
    sid = store.start_session()
    finalize_session(store, FakeLLM().bind(store.tracer), clock, sid)
    assert store.session_info(sid) is None


@pytest.mark.parametrize("query", ["о чём мы говорили вчера?", "what did we talk about yesterday?"])
def test_time_search_finds_yesterdays_episode(store, clock, query):
    yesterday = (clock.now().date() - timedelta(days=1)).isoformat() + "T18:00:00"
    store.add_memory("Conversation: обсуждали ремонт кухни", kind="episode", valid_from=yesterday)
    store.add_memory("Михаил любит чай")
    found = hits(store, query, clock, date_range=parse_time_range(query, clock.now().date()))
    assert found and "ремонт" in found[0].memory.content
    assert found[0].channels["time"] == 0.5


def test_works_without_embeddings(tmp_path, clock):
    db = connect(tmp_path / "m.db")
    store = MemoryStore(db, clock, None)
    store.add_memory("Кота Михаила зовут Барсик", entities=["Барсик"])
    assert hits(store, "как там Барсик?", clock)[0].memory.content.startswith("Кота")


def test_empty_query_does_not_hit_the_embedder(tmp_path, clock):
    calls = []
    db = connect(tmp_path / "m.db")
    store = MemoryStore(db, clock, lambda texts: calls.append(texts) or fake_embed(texts))
    store.add_memory("Что-то важное")
    calls.clear()
    assert hits(store, "   ", clock) == [] and calls == []


def test_embedding_failure_does_not_block_writes_and_backfills(tmp_path, clock):
    state = {"fail": True}

    def flaky(texts):
        if state["fail"]:
            raise RuntimeError("network down")
        return fake_embed(texts)

    db = connect(tmp_path / "m.db")
    store = MemoryStore(db, clock, flaky)
    mid = store.add_memory("Михаил любит горы")
    assert db.execute("SELECT embedding FROM memories WHERE id=?", (mid,)).fetchone()[0] is None
    state["fail"] = False
    assert store.backfill_embeddings() == 1
    assert db.execute("SELECT embedding FROM memories WHERE id=?", (mid,)).fetchone()[0] is not None


def test_retention_decreases_with_age_and_increases_with_importance_access_and_consequences():
    base = retention(30, 0.5, 0, 0)
    assert retention(60, 0.5, 0, 0) < base < retention(5, 0.5, 0, 0)
    assert retention(30, 0.9, 0, 0) > base
    assert retention(30, 0.5, 5, 0) > base
    assert retention(30, 0.5, 0, 3) > base
    assert retention(0, 0.5, 0, 0) == 1.0
    assert abs(retention(30, 0.5, 0, 0) - 0.5) < 1e-9  # one half-life at importance 0.5


def test_decay_lowers_rank_but_never_drops(store, clock):
    store.add_memory("Михаил любит горы", importance=0.5)
    fresh = hits(store, "горы", clock)[0].score
    clock.advance(parse_offset("400d"))
    old = search(store, "горы", now=clock.now(), min_score=0)
    assert old.hits and old.hits[0].score < fresh and old.hits[0].alive < 0.01


def test_touch_refreshes_age(store, clock):
    mid = store.add_memory("Михаил любит горы")
    clock.advance(parse_offset("60d"))
    before = search(store, "горы", now=clock.now(), min_score=0).hits[0].alive
    store.touch([mid])
    after = search(store, "горы", now=clock.now(), min_score=0).hits[0].alive
    assert after > before


def test_led_to_hop_brings_in_the_cause(store, clock):
    cause = store.add_memory("Михаил выгорел на проекте")
    effect = store.add_memory("Михаил решил сменить работу")
    store.link_memories(cause, effect, "led_to")
    result = search(store, "сменить работу", now=clock.now(), min_score=0)
    by_id = {c.memory.id: c for c in result.candidates}
    assert by_id[cause].channels.get("hop", 0) > 0


def test_timeparse():
    today = date(2026, 9, 27)  # Sunday
    assert parse_time_range("что было позавчера", today) == (date(2026, 9, 25),) * 2
    assert parse_time_range("the day before yesterday", today) == (date(2026, 9, 25),) * 2
    assert parse_time_range("на прошлой неделе", today) == (date(2026, 9, 14), date(2026, 9, 20))
    assert parse_time_range("last week", today) == (date(2026, 9, 14), date(2026, 9, 20))
    assert parse_time_range("3 дня назад", today) == (date(2026, 9, 24),) * 2
    assert parse_time_range("3 days ago", today) == (date(2026, 9, 24),) * 2
    assert parse_time_range("what did we talk about last Tuesday?", today) == (date(2026, 9, 22),) * 2
    assert parse_time_range("о чём говорили во вторник?", today) == (date(2026, 9, 22),) * 2
    assert parse_time_range("а в пятницу?", today) == (date(2026, 9, 25),) * 2
    assert parse_time_range("last month", today) == (date(2026, 8, 1), date(2026, 8, 31))
    assert parse_time_range("просто вопрос", today) is None
    assert parse_time_range("just a question", today) is None


def test_as_list_and_as_int_normalize_model_output():
    assert as_list(7) == [7] and as_list(None) == [] and as_list("x") == ["x"] and as_list([1, 2]) == [1, 2]
    assert as_list(["junk", {"a": 1}], dict) == [{"a": 1}]
    assert as_int("#12") == 12 and as_int("7") == 7 and as_int(True) is None and as_int("x") is None


def test_parse_offset():
    assert parse_offset("+2d") == timedelta(days=2)
    assert parse_offset("1d12h") == timedelta(days=1, hours=12)
    assert parse_offset("+0") == timedelta()
    assert parse_offset(3) == timedelta(days=3)
    with pytest.raises(ValueError):
        parse_offset("soon")


def test_trace_tables_live_in_the_memory_db(tmp_path, clock):
    db = connect(tmp_path / "m.db")
    Tracer(db, clock)
    MemoryStore(db, clock, None)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"llm_calls", "retrievals", "memory_events", "memories", "messages", "sessions"} <= tables


def test_config_defaults_and_missing_key(monkeypatch, tmp_path):
    from alice.common.config import ConfigError, load_config
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match=".env.example"):
        load_config(env_file=tmp_path / "missing.env")
    cfg = load_config(require_key=False, env_file=tmp_path / "missing.env")
    assert cfg.short_term == 12 and cfg.session_gap_hours == 3 and isinstance(cfg, Config)
    assert "api_key" not in cfg.public()
