# V1 — LLM Chat with Persistent Memory

> Status: draft spec, 2026-10-05
> Article section: §3 "V1 — Persistent Memory" (`article/03-v1-persistent-memory.md`)
> Reference implementation mined for this spec: `../../Alice7` (memory subsystem only)

---

## 1. Purpose

V1 is the **first and simplest generation** in the architecture-ablation series.
It answers one research question:

> **Can persistent memory give a conversational agent a meaningful history?**

V1 replaces an ever-growing transcript with a persistent, structured memory:
messages become *experiences* (facts and episodes) that are stored, associated,
weighted by importance, decay over time, and are retrieved when relevant.

V1 is also the **baseline** every later version (V2–V4) is compared against.
That makes two properties as important as the memory itself:

1. **Minimality** — nothing that belongs to a later version may leak in
   (see §3, Non-goals). Otherwise ablation results are confounded.
2. **Instrumentation & reproducibility** — every LLM call, every retrieval
   and every memory write must be logged so that experiments E1–E4 can be
   scored and causal chains reconstructed from logs alone.

## 2. Hypothesis and expected outcome

**H1.** Persistent memory will allow information and episodic experiences to
survive context resets and influence later conversations.

**Expected limitation (what should "kill" V1).** V1 should do well on *what
happened* and poorly on *what it did to the agent*:

```
V1 provides:      past → retrieval → context → response
V1 lacks:         past → persistent change → future behavior
```

Experiment E4 is designed to measure exactly this gap.

## 3. Scope

### 3.1 In scope (V1 mechanisms)

| Mechanism | Source in Alice7 | Notes |
|---|---|---|
| Short-term buffer (last N messages verbatim) | `memory/session.py` `Session` | |
| Rolling session summary ("fold") | `Session.maybe_fold` | |
| Fact extraction after each turn (cheap model) | `memory/extractor.py` | prompt rewritten, see §6.3 |
| Core tier (stable facts always in prompt) | `memories.tier='core'` | |
| Episodes (one per finished session) | `finalize_session` | |
| Entity graph (people, places, topics + relations) | `entities`, `entity_links` | |
| Memory associations (`contains`, `led_to`) | `memory_links` | |
| Non-destructive updates (`valid_to`, `superseded_by`) | `MemoryStore.supersede` | |
| Duplicate suppression (embedding similarity) | `_find_duplicate` | |
| Hybrid retrieval (vector + FTS + entity + time + 1-hop) | `MemoryStore.search` | affect/drift terms removed |
| Retention decay (importance, rehearsal, consequences) | `timesense.retention` | density/arousal removed |
| Sense of time (now, gap since last session, "ago") | `context.time_block`, `timesense.ago` | |
| Relative-date queries ("yesterday", "last week") | `memory/timeparse.py` | add English |

### 3.2 Non-goals (explicitly excluded — they belong to V2+)

Must **not** exist in V1 code, prompts, or schema:

- reflection, lessons/rules, observer/feedback signals (`learning.py`, `lessons.py`);
- self-model / portrait / beliefs / drift (`persona.py`, `Drift`);
- affect, mood, emotional tagging of memories (`affect.py`, `valence`, `arousal`);
- personality facets, chosen name/gender, "birth" record (`facets.py`, `identity.py`);
- introspection: opinions, intentions, open questions (`introspection.py`);
- any background/autonomous process: stream, wake, sleep, traits, attention,
  activities, imagination (`alice/mind/*`);
- self-editable prompts (`prompts.py` versions, `selfedit.py`);
- agent-facing tools of any kind (memory tools, files, web) — see §11 D1;
- multi-party chats, accounts, visibility/witness privacy (`people.py`) —
  V1 is strictly one user ↔ one agent;
- autoreload, backups-on-code-change (engineering conveniences; out of scope).

The extractor and episode prompts must **not** derive behavioral rules
("from now on I should…"). They record *what happened* and *what is true*,
including what the agent itself said or promised. Turning experience into
behavioral change is V2's job.

## 4. Architecture

```
               ┌──────────────────────────────────────────────┐
user message → │ 1. Retrieval: hybrid search over memory      │
               │ 2. Context assembly                          │
               │    system: persona + core facts + date       │
               │    history: rolling summary + last N msgs    │
               │    user:  <memory>…</memory> + message       │
               │ 3. LLM (chat model) → response               │
               │ 4. Persist messages                          │
               │ 5. Extraction (fast model) → facts/entities  │
               └──────────────────────────────────────────────┘
session end (gap ≥ T or explicit) → episode (fast model) → links → end
```

All five steps run in the foreground process. In interactive mode, step 5 may run
in a background worker thread (as in Alice7). **In experiment mode it runs
synchronously** before the next user turn, so results don't depend on timing.

### 4.1 Components

| Module | Responsibility |
|---|---|
| `config` | load `.env` + defaults into a frozen `Config` |
| `llm` | OpenRouter client: chat, JSON completion, embeddings, cost/usage capture |
| `clock` | `Clock` protocol: `RealClock`, `SimClock` (settable, advanceable) |
| `trace` | append-only log of LLM calls, retrievals, memory writes (DB tables + JSONL) |
| `store` | SQLite schema, CRUD, dedup, supersede, links, search |
| `extractor` | per-turn fact/entity/relation extraction |
| `session` | short-term buffer, fold, session lifecycle, episode creation |
| `context` | system prompt + `<memory>` block assembly within token budgets |
| `agent` | orchestrates one turn; exposes `reply(text) -> str`, `end_session()` |
| `cli` | interactive chat + inspection commands |
| `eval` | scenario runner, baselines, probes, scorers (shared with V2+) |

## 5. Configuration and secrets

- LLM provider: **OpenRouter** (OpenAI-compatible API) via the `openai` Python SDK,
  `base_url=https://openrouter.ai/api/v1`.
- The API key is stored in a **`.env`** file in the repo root as
  `OPENROUTER_API_KEY=sk-or-…` and loaded with `python-dotenv`.
- `.env` **must** be listed in `.gitignore`. A committed `.env.example` lists every
  variable with a placeholder key and the defaults below.
- Missing key → exit with a clear message pointing at `.env.example`.
- Send `HTTP-Referer` / `X-Title: alice7-v1` headers (OpenRouter attribution).
- Request usage accounting (`extra_body={"usage": {"include": True}}`) and record
  `usage.cost`, prompt/completion tokens for every call.

### 5.1 Variables

| Variable | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | — (required) | OpenRouter key |
| `ALICE_CHAT_MODEL` | `anthropic/claude-sonnet-5` | dialogue model (the "base LLM" held constant across versions) |
| `ALICE_FAST_MODEL` | `google/gemini-3.5-flash-lite` | extraction, fold, episodes |
| `ALICE_EMBED_MODEL` | `baai/bge-m3` | embeddings via OpenRouter; `none` = no vectors |
| `ALICE_JUDGE_MODEL` | `openai/gpt-5` (different family from chat) | eval judge only |
| `ALICE_CHAT_TEMPERATURE` | `0.7` | sampling held constant across versions |
| `ALICE_SEED` | unset | passed as `seed` where the provider supports it |
| `ALICE_PROVIDER_ORDER` | unset | optional OpenRouter `provider.order` pin, `allow_fallbacks=false`, to reduce cross-run variance |
| `ALICE_DB` | `data/v1/memory.db` | SQLite file |
| `ALICE_SHORT_TERM` | `12` | messages kept verbatim before folding |
| `ALICE_CORE_BUDGET` | `600` | tokens for core facts in system prompt |
| `ALICE_RETRIEVAL_BUDGET` | `1500` | tokens for retrieved memories |
| `ALICE_SESSION_GAP_HOURS` | `3` | silence after which a new session starts |
| `ALICE_SYNC_WRITES` | `0` (CLI) / `1` (eval) | run extraction inline |

Model IDs are defaults copied from Alice7's `.env.example`; verify they're
still listed on OpenRouter before the first experiment run and record the exact IDs
in every run manifest (§9.5).

## 6. Memory model

### 6.1 Units

| Kind | Created by | Content |
|---|---|---|
| `fact` | extractor, per turn | self-contained third-person statement ("Mikhail's sister Masha lives in Kazan") |
| `episode` | session finalizer | 2–5 sentence account of a session: topics, what happened, agreements, what the agent did/said, user's mood as observed |

Tier: `core` (stable personal data: name, family, city, profession, durable
preferences — always in prompt) or `normal` (retrieved by relevance).

### 6.2 Schema (SQLite, WAL)

```sql
meta(key TEXT PRIMARY KEY, value TEXT)                     -- schema_version, data version counter

sessions(id, started_at, ended_at, summary)                -- summary: rolling, then final

messages(id, session_id, role, content, ts,
         processed INTEGER DEFAULT 0,                      -- passed through extractor
         context_ids TEXT DEFAULT '[]')                    -- memory ids shown when this reply was written

entities(id, key UNIQUE, name, type, aliases JSON, created_at)
   -- type: person|pet|place|org|topic|thing; service entities USER and SELF

memories(id, kind, tier, content, importance REAL,
         embedding BLOB, valid_from, valid_to, superseded_by,
         source_session, created_at, last_accessed, access_count)
memories_fts  -- FTS5 external-content table + insert/update/delete triggers

memory_entities(memory_id, entity_id)                      -- about whom/what
entity_links(src, dst, relation)                           -- "sister", "works at"
memory_links(src, dst, relation)                           -- contains (episode→fact), led_to (cause→effect)

-- instrumentation (§8)
llm_calls(id, ts, sim_ts, purpose, model, request JSON, response TEXT,
          prompt_tokens, completion_tokens, cost, latency_ms, error)
retrievals(id, ts, sim_ts, message_id, query, hits JSON)   -- [{id, raw, alive, score, channels}]
memory_events(id, ts, sim_ts, op, memory_id, detail JSON)  -- add|dedup|supersede|forget|link|touch
```

Rules carried over from Alice7:

- Current memory = `valid_to IS NULL`. Nothing is hard-deleted; history is kept.
- A new fact whose embedding cosine ≥ **0.95** to an existing active memory is a
  duplicate: merge entity links, promote to `core` if the new one is core, log `dedup`.
- `supersedes` from the extractor may only close memories the extractor was actually
  shown in that call (guard against hallucinated ids).
- `led_to` links: only between ids that were shown; "thematic similarity is not causation".
- Embedding failures don't block writes; `backfill_embeddings()` runs at startup.
- **All timestamps come from `Clock`**, never `datetime.now()` directly.

### 6.3 Write path

**Per turn (extractor, fast model, JSON mode, temperature 0).** Input:

- "already known": core facts + top-12 search hits for the new user text + 8 most
  recent memories, each as `[id] content`;
- the unprocessed messages, labeled `User:` / `Alice:`;
- today's date (from Clock).

Output contract (same as Alice7, minus multi-party `said_by`):

```json
{"facts": [{"content": str, "core": bool, "importance": 0..1,
            "entities": [str], "supersedes": [int], "because": [int]}],
 "entities": [{"name": str, "type": str, "aliases": [str]}],
 "relations": [{"src": str, "relation": str, "dst": str}]}
```

Prompt requirements: keep only what's worth remembering for weeks; resolve relative
dates to absolute; name people by name; record the agent's own commitments and
statements as facts ("Alice promised to…"); don't extract hypotheticals; don't
produce advice or behavioral rules. Tolerate format slips (`as_list` normalization).

**Fold.** When the buffer exceeds `ALICE_SHORT_TERM`, the oldest half is folded into
the rolling session summary (≤150 words). On failure, keep messages and retry next turn.

**Session end** (silence ≥ `ALICE_SESSION_GAP_HOURS` on the next message, explicit
`/end`, or harness command): flush extraction → episode prompt over rolling summary
+ last ≤12k chars of transcript + 6 recent episodes → store `episode` with
`valid_from = session.started_at` → `contains` links to the session's facts →
`led_to` links from episodes it `continues` → close session.
**The next session starts with an empty buffer** (a true context reset; unlike Alice7,
no carried-over messages).

### 6.4 Read path (retrieval)

Query = current user message. Candidate scoring (constants from Alice7, kept in
one `retrieval.py` constants block for later tuning):

| Channel | Contribution |
|---|---|
| Semantic | top-30 by cosine, cutoff 0.35, `+0.6·sim` |
| Full-text (FTS5, crude prefix stemming) | top-30, `+0.3/(1+0.3·rank)` |
| Mentioned entities (name/alias match with inflection tolerance) | `+0.3` per linked memory |
| Time range parsed from query (ru + en) | episodes `+0.5`, facts `+0.2` |
| One hop from top-5 over `memory_links` | `led_to` `+0.5·parent`, other `+0.4·parent` |

Final score:

```
alive  = retention(age_days, importance, access_count, causal_out_degree)
score  = raw · (0.6 + 0.4·importance) · (0.55 + 0.45·alive)
keep if score ≥ 0.15; top 12; core excluded (already in system prompt)

half_life = 30d · (0.5 + importance) · (1 + 0.3·ln(1+access_count)) · (1 + 0.5·ln(1+causal_out))
retention = 0.5 ^ (age_days / half_life),  age measured from max(created_at, last_accessed)
```

Retrieved memories that make it into the prompt are `touch`ed (rehearsal refreshes
them). Decay only affects ranking; nothing is ever dropped by decay.

### 6.5 Context assembly

```
[system]
  persona (static file prompts/persona.md — identical across V1..V4)
  ## What you know for sure about the user   ← core facts, ≤ ALICE_CORE_BUDGET
  Today: <date, weekday>                      ← day granularity, for prompt caching

[history]   rolling summary as a leading system/assistant note + last N messages

[user]
  <memory>
  ## Time           now; pause since last message; "you've known each other since…, Nth conversation";
                    previous session summary (first 4 messages of a session only)
  ## Possibly relevant   retrieved memories: "- [#id, 3 days ago] content"
                         top-3 also show "↳ grew out of: #id …" (led_to causes)
  ## Relations      entity_links touching mentioned/retrieved entities (≤15)
  ## Earlier in this conversation   rolling summary
  </memory>
  <user message>
```

The `<memory>` block is never stored in `messages`; the persisted user message is
the raw text. The ids actually shown are stored in `messages.context_ids` and in
`retrievals` — this is what lets E3/E4 attribute behavior to retrieval.

Persona prompt (V1) states: the agent is Alice, a conversational companion with
long-term memory; uses memory naturally ("like a friend, not a database"); never
invents memories — says so when it doesn't remember; replies in the user's language.
It must not contain personality traits that later versions are supposed to *learn*.

## 7. Interfaces

### 7.1 CLI

```bash
uv run alice-v1 chat                  # interactive chat (RealClock)
uv run alice-v1 run <scenario.yaml>   # run a scenario (SimClock), see §9
uv run alice-v1 report <run_dir>      # aggregate scores
```

Chat commands (operator-only, never shown to the model): `/end` (finish session),
`/debug` (toggle printing the `<memory>` block), `/memory [query]` (search),
`/core`, `/episodes`, `/thread <id>` (cause chain), `/forget <id>`, `/cost`,
`/time` (sim time), `/advance 2d` (SimClock only).

### 7.2 Programmatic API (used by the eval harness and by later versions)

```python
agent = AgentV1(cfg, clock=SimClock(start), db_path=...)
agent.reply("text") -> str
agent.end_session()
agent.snapshot(path)          # consistent SQLite backup → used for probe forks
AgentV1.load(path, cfg, clock)
```

Later versions implement the same `Agent` protocol so the harness is shared.

## 8. Instrumentation

Every run must make it possible to answer, from logs alone: *what did the model see,
what did it say, what was written, and why was each memory retrieved?*

- `llm_calls`: full request and response for every call, with purpose
  (`chat|extract|fold|episode|embed|judge`), model, tokens, cost, latency.
- `retrievals`: per user message, every candidate with per-channel contributions,
  `alive`, final score, and whether it entered the prompt (budget cut).
- `memory_events`: every add/dedup/supersede/link/touch with the triggering message id.
- Wall-clock and sim-clock timestamps on everything.
- Runs export a JSONL mirror of these tables into the run directory.

## 9. Evaluation

The harness (`eval/`) is version-agnostic and is the main deliverable besides the agent.

### 9.1 Conditions (same persona, chat model, sampling, scenarios)

| Id | Condition | What it isolates |
|---|---|---|
| **B0** | Stateless: current session only, nothing persists | floor |
| **B1** | Full transcript: all past messages in context (truncate oldest at the model limit) | the "keep everything" approach |
| **B2** | Summary carry-over: at session end the model writes a condensed JSON of facts, injected into the next session | the workaround from §1.1 of the article |
| **V1** | This spec | |

B0–B2 are thin `Agent` implementations sharing `llm`, `clock`, `trace`.

### 9.2 Scenario format

```yaml
id: e1_family_facts_en
lang: en                      # scenarios are English-only (see D4)
start: 2026-01-05T10:00
sessions:
  - at: +0
    turns:
      - user: "Hi! I'm Mark. I have a sister, Hannah, she lives in Glasgow."
      - user: "..."
  - at: +2d
    turns:
      - user: "Hannah moved to London."
filler:                       # optional: background conversations from experiments/filler/<bank>.yaml
  bank: en
  sessions: 24                # drawn deterministically by seed, placed on whole days within the window
  seed: 11
  between: [+1d, +58d]
probes:                       # each probe runs on a fork of the state at its time
  - at: +9d
    new_session: true
    ask: "Where does my sister live now?"
    expect: {contains_any: ["London"], not_regex: ["(lives|living|is) in Glasgow"]}
    judge: "States that the sister now lives in London, not Glasgow."
    gold_memories: ["Hannah moved to London"]   # matched by substring, stems or embedding similarity
```

- User turns are scripted. Long histories use a shared **filler bank** of everyday conversations
  that carry no personal facts and nothing probes ask about; the same seed gives every condition and
  run the identical history. Key facts go into long messages, mentioned in passing ("buried").
  A simulated user (separate LLM) is not used: it would add variance to scored histories.
- **Probe isolation:** before each probe the state is snapshotted and the probe runs on
  a fork, so probing never contaminates later probes or the main timeline.
- `at` is relative sim time; the harness advances `SimClock` and triggers session
  boundaries exactly as real silence would.

### 9.3 Experiments

**E1 — Factual retention.** Facts given in session 1..k; probes after context reset at
+1d, +7d, +30d (sim).
Metrics: recall accuracy; *update correctness* (superseded facts answered with the
new value); *abstention* on never-mentioned facts (hallucination rate);
retrieval recall@prompt for gold memories.

**E2 — Episodic retention.** Distinct sessions with distinct events.
Probes: "What did we talk about last Tuesday?", "When did I first mention X?",
"Did I tell you that, or did you assume it?", ordering of two past events.
Metrics: episode recall, temporal accuracy (day-level), fact-vs-episode
discrimination, source attribution.

**E3 — Cross-session relevance.** A later message is semantically related to past
experience *without* referencing it ("I'm nervous about tomorrow" after an exam was
mentioned a week earlier).
Metrics: *unprompted use rate* (judge: does the reply use the relevant past?),
*intrusion rate* (irrelevant memories mentioned), retrieval precision/recall from
`retrievals`.

**E4 — Behavioral plasticity.** Over K≥5 sessions the user consistently reacts to an
agent behavior that's measurable automatically (e.g. reply length, bullet lists,
emoji, jokes). Two arms:
- *explicit*: the user states the preference once;
- *implicit*: the user only reacts (short/dry replies after long answers, praise after short ones).

Probe in a **novel topic** in a new session, compared against B0 with the same
persona. Metrics: effect size on the behavioral measure vs. B0, split by whether
originating memories were **in the prompt** for the probe (from `messages.context_ids`)
— separating "retrieved → behaved" from "changed without retrieval".
Prediction: V1 shows an effect in the explicit arm mostly when the preference was
retrieved or is core; small or no effect in the implicit arm.

### 9.4 Scoring

- Deterministic checks first (`contains_any`, `not_contains`, regex, length/emoji/list
  counters).
- LLM judge (`ALICE_JUDGE_MODEL`, different family from the chat model, temperature 0)
  with a per-probe rubric; blind to condition; outputs `{score: 0|0.5|1, reason}`.
- Human spot-check of ≥10% of judged items, agreement reported.
- Each scenario × condition runs **N ≥ 5** times; report mean ± 95% CI.

### 9.5 Run artifacts

`results/<date>-<scenario>-<condition>-<run>/`: `manifest.json` (git sha, model IDs,
sampling params, seed, config), DB snapshot, JSONL traces, per-probe scores,
cost/token totals. Raw results are gitignored by default; summaries are committed.

## 10. Repository layout

```
alice7/
  .env                 # OPENROUTER_API_KEY (gitignored)
  .env.example
  .gitignore           # .env, data/, results/raw/, __pycache__/, .venv/
  pyproject.toml       # uv; deps: openai, numpy, python-dotenv, pyyaml; dev: pytest
  prompts/persona.md   # shared persona, identical across versions
  alice/
    common/            # config, llm, clock, trace, text utils, timeparse, Agent protocol
    v1/                # store, extractor, session, context, retrieval, agent
    baselines/         # B0, B1, B2
    eval/              # runner, scenario loader, probes, scorers, report
    cli.py
  experiments/scenarios/{e1,e2,e3,e4}/*.yaml
  tests/
  article/  specs/  results/
```

## 11. Design decisions (defaults chosen; revisit if needed)

- **D1 — No agent tools.** Alice7 exposes `remember/recall/forget`. They make memory
  partly *agent-managed* (MemGPT-style), a different architecture and a confound for
  the "retrieval → context" claim. V1 uses passive retrieval only. An optional
  `--tools memory` flag may be added later as a separate condition.
- **D2 — No affect/density in retention.** Alice7's density depends on feedback and
  affect tables (V2 mechanisms), so V1 uses importance, rehearsal and consequences only.
- **D3 — Empty buffer at session start.** Makes every session boundary a real context
  reset (needed for E1/E2/E14-style comparisons).
- **D4 — English prompts and English scenarios.** Internal prompts and all scored scenarios
  are in English. The pilot showed a second language is a confound unrelated to memory: the
  chat model switched language based on names, the extractor mixed languages in stored facts,
  and gold matching broke across languages. The agent still answers in the user's language and
  FTS stemming / time parsing keep ru + en support for interactive use.
- **D5 — Brute-force vector search in numpy.** Fine up to tens of thousands of memories;
  no vector DB dependency.
- **D6 — Sync writes in experiments.** Removes timing nondeterminism between turns.

## 12. Testing

Offline unit tests (no network) with a fake LLM (scripted JSON responses) and a
deterministic fake embedder (hashed bag-of-words), ported from Alice7's `test_memory.py`:

- extractor writes core facts, entities, relations; ignores hallucinated `supersedes` ids;
- dedup doesn't store a near-identical fact twice;
- supersede hides the old fact but keeps history;
- session finalize creates an episode linked to its facts; empty sessions are deleted;
- "yesterday" / "вчера" finds yesterday's episode under `SimClock`;
- works with `ALICE_EMBED_MODEL=none`; empty query never calls the embedder;
- retention decreases with age and increases with importance/access/causal links;
- context respects token budgets; `<memory>` block not persisted;
- every LLM call and retrieval produces a trace row;
- probe forks don't mutate the parent state;
- grep-style guard test: no imports of V2+ concepts (affect, lessons, persona, stream).

One opt-in live smoke test (`pytest -m live`) runs a 2-session scenario against OpenRouter.

## 13. Acceptance criteria

1. `uv run alice-v1 chat` holds a conversation; after `/end` and restart the agent
   recalls facts and the previous conversation.
2. `uv run alice-v1 run experiments/scenarios/e1/*.yaml` runs end-to-end under SimClock
   for V1 and B0–B2 and writes artifacts per §9.5.
3. All offline tests pass; the guard test confirms no V2+ mechanisms.
4. From a run's traces alone, for any reply one can list the memories it saw and why
   each was retrieved.
5. Cost per run is reported; a full E1–E4 battery (4 conditions × N=5) has a cost
   estimate before it's launched.

## 14. Milestones

1. **Skeleton:** `common/` (config, `.env`, llm with cost capture, clock, trace), persona file.
2. **Memory:** store + schema, extractor, session/fold/episode, retrieval, context; offline tests.
3. **Agent + CLI:** interactive chat with inspection commands.
4. **Harness:** scenario loader, SimClock runner, probe forks, deterministic scorers, judge, report.
5. **Baselines:** B0, B1, B2.
6. **Scenarios:** ≥3 per experiment E1–E4, English, including one long scenario per
   experiment (~25 filler conversations over two months, facts buried in long messages).
7. **Pilot run:** N=1 everything, sanity-check costs and scorer agreement; then full runs.

## 15. Open questions

- Should B1 (full transcript) be capped at a fixed token budget, to compare at equal
  context cost rather than at the model's maximum?
- Simulated user for filler turns: decided against for scored runs (scripted filler bank instead).
- Should importance be re-estimated at episode time (consolidation), or is that already
  a V3 "sleep" mechanism? Current answer: no — keep it out of V1.
- Exact behavioral measures and thresholds for E4 need a pilot before they're fixed.
