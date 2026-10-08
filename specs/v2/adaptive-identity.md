# V2 — Adaptive Identity

> Status: draft, decisions of 2026-10-08 applied (no facets; affect moved to V3; B3 added;
> reflection on the chat model). No code yet. Branch `v2`.
> Article section: §4 "V2 — Adaptive Identity" (`article/04-v2-adaptive-identity.md`)
> Builds on: V1 (`specs/v1/llm-chat-with-better-memory.md`), frozen at `ae1187f`
> Reference implementation mined for this spec: `../../Alice7` (`memory/learning.py`, `lessons.py`,
> `persona.py`, `introspection.py`); `affect.py` and everything under `alice/mind/` stay out (V3+)

---

## 1. Purpose

V2 is the second generation in the ablation series. It answers:

> **Can accumulated experience change the agent itself?**

V1 gave the agent a history. Its main limitation, observed in pass 1 (article §3, E4):

```
past → retrieval → context → response            present in V1
past → persistent change → future behavior       absent in V1
```

V1's episodes *did* record the user's reactions ("Nina gave a resigned assent"), and those
episodes were in the prompt, but they were stored as observations about the user's mood, not as
feedback about the agent's behavior. No memory condition adapted to a preference that was only
shown, never stated.

V2 adds the smallest set of mechanisms that turns experience into persistent internal change:

```
agent behavior → user reaction → feedback signal → reflection → lesson / self-model
             → always-present internal state → changed behavior in a novel context
```

In terms of human memory systems, V1 has the declarative ones: working memory (the buffer),
semantic (facts) and episodic (episodes). V2 adds non-declarative and self-related ones:
**procedural** (lessons/habits: what I now do differently, without recalling where I learned it),
**prospective** (intentions: what I mean to do), and **autobiographical self-knowledge** (portrait,
beliefs, opinions). Emotional memory comes with affect in V3; implicit associative memory that
can't be read as text is V4. V1's declarative memory is reused unchanged.

V2 must still be minimal: nothing from V3+ (background processes, autonomy, sleep, affect) may
leak in.

## 2. Hypothesis and expected outcome

**H2.** Persistent reflection over experience will produce behavioral tendencies that generalize
beyond direct retrieval of the originating events.

Operational predictions:

1. **E4 implicit arm flips.** On the *same* E4 scenarios where no condition adapted, V2 adapts:
   bullet counts / reply length on a novel-topic probe differ from B0 and V1.
2. **Change without retrieval.** The effect holds on probes where none of the originating memories
   (the sessions with the reactions) were in the prompt, because the change lives in lessons and the
   self-model, which are always present.
3. **Revision, not accumulation.** After contradictory experience (E6), V2 changes behavior and
   retires/weakens the old lesson instead of holding two contradictory active rules.
4. **Traceability.** For a changed behavior, the chain event → reflection → lesson → later behavior
   can be reconstructed automatically from logs (E7).
5. **No regression on memory.** E1–E3 scores stay within noise of V1.

**Expected limitation (what should "kill" V2).**

- All change is **event-driven**: between sessions nothing happens. State at t₀ and at t₀ + 12 h of
  silence is identical except for decay computed on read. → motivates V3.
- The identity is **textual**: lessons and portrait are text the LLM reads. Removing the self-model
  text should remove most of the acquired behavior (E12), and a false self-description should win
  over lived experience (E13). This is the first measurement of what V4 is meant to fix.

## 3. Scope

### 3.1 In scope (V2 mechanisms)

| Mechanism | Source in Alice7 | Notes |
|---|---|---|
| **All of V1**, unchanged | `alice/v1/*` | imported, not copied; V1 prompts and memory schema untouched |
| Observer: per-turn reaction signal on the *previous* reply | `learning.Observer` | fast model; reads its own raw reply, no form hints (D11) |
| Feedback log | `lessons.add_feedback` | signal −1..1, kind, what, hint |
| Explicit instruction → lesson at once | `Observer.observe` (`explicit`) | confidence 0.8 |
| Self-decisions → `self` lessons | `Observer` (`self`) | "I call the user Misha" |
| Reflector: lesson operations from accumulated feedback | `learning.Reflector` | add / reinforce / weaken / revise / retire |
| Lessons with confidence dynamics, situation conditions | `lessons.LessonStore` | habits in system prompt, situational in `<memory>` |
| Self-model: portrait + weighted beliefs, versioned | `persona.Persona` | rewritten at session end, 1–3 changes |
| Opinions (topic stances), versioned | `introspection` (`opinion`) | retrieved by relevance; needed for E13 |
| Persistent intentions | `introspection` (`intention`) | surfaced at session start; closed by the observer |

### 3.2 Non-goals

Must **not** exist in V2 (they belong to V3+ or are out of the series):

- any background or autonomous process: tick, stream, drift thoughts, wake, pressure, spontaneous
  introspection between turns, autonomous initiation (the agent speaks only in reply);
- sleep, consolidation, memory rewriting (`mind/sleep.py`); importance re-estimation;
- traits that change mechanics (`mind/traits.py`), attention, activities, imagination;
- self-editable prompts (`prompts.py` versions, `selfedit.py`);
- agent-facing tools of any kind (memory, `think`, `done`, files, web) — V1 D1 still holds;
- multi-party chats, people, visibility (`people.py`);
- affect: appraisal, mood, emotional tagging of memories (`affect.py`) — moved to V3, where
  time-dependent processes live (D3);
- name/gender "birth" record and chosen identity (`identity.py`); personality facets (D4);
- any change to V1 memory: extractor, episode, retrieval channels, retention formula.

Inherited rule, restated: V1's extractor and episode prompts keep recording *what happened*. Turning
experience into rules is done **only** by the new V2 components, so V2 − V1 differences are
attributable to them.

## 4. Architecture

```
               ┌────────────────────────────────────────────────────────────┐
user message → │ 1. Retrieval: V1 hybrid search                             │
               │    + situational lessons, relevant opinions (V2)           │
               │ 2. Context assembly                                        │
               │    system: persona + core facts                            │
               │            + self-model (portrait) + habits          (V2)  │
               │            + date                                          │
               │    history: rolling summary + last N msgs                  │
               │    user:  <memory> … + lessons for this situation          │
               │           + on your mind (intentions) …</memory> + message │
               │ 3. LLM (chat model) → response                             │
               │ 4. Persist messages + shown state ids (V2: turn_state)     │
               │ 5. Extraction (V1, fast model)                             │
               │ 6. Self-observation (V2, fast model): reaction to the      │
               │    previous reply, self-decisions, commitments, fulfilled  │
               │    intentions                                              │
               │ 7. Mid-session reflection if ≥ 6 unreflected signals       │
               └────────────────────────────────────────────────────────────┘
session end → V1 episode → Reflector (lessons) → Self-review (portrait, beliefs,
              opinions, intentions) → close
```

Steps 5–7 run synchronously in experiment mode (V1 D6), in a worker thread interactively. The
session-end steps run inside `end_session()`; there is no timer — a session still ends only when
the next message arrives after the gap, or explicitly.

### 4.1 Components

| Module | Responsibility |
|---|---|
| `v2/agent.py` | `AgentV2`: wraps V1 components, adds steps 6–7 and the session-end chain |
| `v2/observer.py` | per-turn self-observation call (reaction, self, commitments, fulfilled) |
| `v2/lessons.py` | `LessonStore`: CRUD, confidence dynamics, dedup, habits, situational match, events |
| `v2/reflector.py` | lesson operations from feedback + session summary |
| `v2/selfmodel.py` | portrait + beliefs (versioned), opinions (superseding chain) |
| `v2/intentions.py` | open / done / dropped intentions, surfacing rules, expiry |
| `v2/context.py` | extends V1 `ContextBuilder` with the V2 sections; enforces budgets |
| `v2/schema.py` | V2 tables, created next to the V1 schema in the same SQLite file |
| `v2/switches.py` | per-mechanism on/off (§5.2), used by ablation conditions and probe forks |

V1 code is not edited. If V2 needs a hook that V1 doesn't expose (e.g. a retention multiplier), V2
subclasses or wraps the V1 class; if that's impossible without editing V1, the change goes into the
spec discussion first (§15).

## 5. Configuration

### 5.1 New variables

| Variable | Default | Meaning |
|---|---|---|
| `ALICE_REFLECT_MODEL` | = `ALICE_CHAT_MODEL` | Reflector and self-review ("the agent thinking about itself") |
| `ALICE_OBSERVE_MODEL` | = `ALICE_FAST_MODEL` | per-turn self-observation |
| `ALICE_DB` | `data/v2/memory.db` | |
| `ALICE_LESSONS_BUDGET` | `400` | tokens for habits in the system prompt |
| `ALICE_PORTRAIT_WORDS` | `180` | max portrait length |
| `ALICE_REFLECT_EVERY` | `6` | unreflected signals that trigger mid-session reflection |
| `ALICE_V2_SWITCHES` | `all` | comma list, e.g. `lessons,intentions` (no `selfmodel`) |

All V2 background-model calls run at temperature 0. The chat model keeps V1's 0.7.

### 5.2 Switches

Each mechanism can be turned off independently, both for a whole run (build-time ablation: the
mechanism never existed) and on a probe fork (probe-time ablation: it existed, then was removed):

| Switch | Off means |
|---|---|
| `lessons` | no observer feedback, no reflector, no lessons in prompt |
| `selfmodel` | no portrait, beliefs or opinions written or shown |
| `intentions` | none created or shown |

With every switch off, `AgentV2` must behave exactly like `AgentV1` (tested: identical requests to
the chat model given the same LLM fakes).

## 6. Mechanisms

### 6.1 Schema additions (SQLite, same file as V1)

```sql
feedback(id, session_id, assistant_msg_id, user_msg_id, signal REAL,   -- −1..1
         kind TEXT,          -- correction|frustration|praise|engagement|disengagement|neutral
         target TEXT,        -- NULL at write time; classified from `what` by the judge at report time
         what TEXT, hint TEXT, explicit INTEGER, reflected INTEGER DEFAULT 0, ts, sim_ts)

lessons(id, category,        -- style|behavior|user_model|self
        rule TEXT, situation TEXT,       -- situation '' = always
        confidence REAL, evidence INTEGER, status,   -- active|retired
        embedding BLOB, situation_embedding BLOB, created_at, updated_at)
lesson_events(id, lesson_id, op,         -- add|reinforce|weaken|revise|retire
              confidence REAL, note TEXT,
              feedback_ids JSON,         -- which signals caused it   (E7 chain)
              message_id INTEGER,        -- for explicit/self lessons: the triggering message
              llm_call_id INTEGER, ts, sim_ts)

portraits(id, content, changes, session_id, llm_call_id, created_at)
beliefs(id, portrait_id, text, weight REAL, parent_id)   -- parent: same belief in previous version

opinions(id, topic, content, stance REAL,    -- −1..1, toward the topic
         embedding BLOB, session_id, superseded_by, created_at)

intentions(id, content, due_from, due_to,    -- optional resolved time window
           source,                           -- commitment|self_review
           message_id, session_id, status,   -- open|done|dropped
           closed_by_message, created_at, closed_at)

turn_state(message_id PRIMARY KEY,    -- assistant message
           portrait_id, lesson_ids JSON, opinion_ids JSON, intention_ids JSON,
           switches JSON)             -- exactly what V2 state the reply was written with
```

V1 tables are not altered.

### 6.2 Lessons

Carried over from Alice7 (`lessons.py`), constants in one block:

| Constant | Value | Meaning |
|---|---|---|
| `ACTIVE` | 0.55 | habit threshold: lesson enters the system prompt |
| `SITUATIONAL_MIN` | 0.45 | situational lessons may be shown from here |
| `SITUATION_SIM` | 0.50 | cosine of query to `situation` to count as "this situation" |
| `SAME_LESSON_SIM` | 0.88 | a new lesson this close to an active one reinforces it instead |
| `RETIRE` | 0.20 | below this a weakened lesson is retired |
| explicit / self | 0.80 | initial confidence of a directly stated instruction or own decision |
| reflector `add` | ≤ 0.60 | hypotheses can't start as habits — repetition makes them habits |

```
reinforce: c ← min(0.97, c + (1 − c) · 0.35)
weaken:    c ← c · 0.6;  c < 0.20 → retire
```

A lesson is an instruction to act ("Answer in connected prose, without lists"), not a fact about
the user. Facts about the user's life stay in V1 memory. `user_model` lessons ("He loses interest
in long technical detours") are allowed: they are interpretations, not facts.

**Habits** (active, no situation) go into the system prompt, highest confidence first, within
`ALICE_LESSONS_BUDGET`. **Situational** lessons go into `<memory>` (top 3 by `sim · confidence`).
Confidence numbers are never shown to the model; habits are phrased plainly.

### 6.3 Self-observation (per turn)

One fast-model call per user turn (Alice7's `Observer`, without the facet and trait parts). Input:

- the agent's **previous** reply, verbatim (up to 4,000 characters), and nothing computed from it:
  no counts of words, list items or emoji (D11);
- the new user message(s);
- active lessons `[id] rule`, open intentions `[id] content`;
- today's date.

Output contract:

```json
{"reaction": {"signal": -1..1, "kind": str, "what": str, "hint": str,
              "explicit": bool, "category": "style|behavior"} | null,
 "self": [{"rule": str}],                      // the agent's own decisions about itself, 1st person
 "commitments": [{"content": str, "when": str}],   // what the agent promised or intends to do
 "fulfilled": [int],                           // ids of open intentions this exchange carried out
 "replaces": [int]}                            // lessons the explicit instruction overrides
```

Rules (from Alice7):

- `explicit` and `hint` → lesson at 0.8 immediately; `replaces` retires only lessons shown in the call.
- Non-explicit with |signal| ≥ 0.2 → `feedback` row; nothing else happens until reflection.
- `reaction` is about the previous reply only; first message of a session → `null`.
- Hallucinated ids (`replaces`, `fulfilled` not in the input) are ignored.

The observer's prompt states that ordinary continuation of the conversation is neutral (signal 0),
to keep it from reading praise into politeness. `what` is free text ("what in your reply the
reaction was about"); the prompt gives no list of candidate aspects, because any such list
(length, lists, tone…) would point at the dimensions the scenarios manipulate.

### 6.4 Reflection

**Reflector** (`ALICE_REFLECT_MODEL`) runs at session end, and mid-session when ≥ 6 unreflected
signals accumulate, and only when there are unreflected signals: reflecting over a summary alone
would turn retold events into rules with no evidence about the agent's behavior. Each operation
cites the reactions that support it (`because`); uncited operations are attributed to all
reactions consumed. Input: current lessons with confidence and evidence count, unreflected feedback
(each with the full reply it reacted to, up to 1,500 characters, and the user's reaction), the
session summary. Alice7 cut replies to 300 characters here, which would hide exactly the form of a
long answer. Output:
≤ 6 operations `{op, id, category, rule, situation, confidence, why}`. Prompt principles carried
over: generalize to a pattern, phrase as an instruction, also reinforce what worked, prefer revising
an existing lesson to adding a near-duplicate, no facts about the user's life.

Each applied op writes `lesson_events` with the `feedback_ids` it consumed and the `llm_call_id`.

### 6.5 Self-model

**Self-review** (`ALICE_REFLECT_MODEL`), at session end after the Reflector. One call, output:

```json
{"portrait": str, "changes": str,
 "beliefs": [{"text": str, "weight": 0..1, "continues": int | null}],
 "opinions": [{"topic": str, "content": str, "stance": -1..1, "replaces": int | null}],
 "intentions": [{"content": str, "when": str}]}
```

- **Portrait** — "who I am", first person, ≤ 180 words, 1–3 changes per session, or the previous
  text unchanged. Starts empty: the shared persona has no traits, and the first portrait is written
  after the first session. Prompt carries Alice7's guards: change gradually; rely on what actually
  happened; you are not a mirror of the user; don't invent biography; communication rules are kept
  separately — don't list them.
- **Beliefs** — 4–8 weighted statements; `continues` links to the same belief in the previous
  version (only ids that were shown). This makes belief drift measurable (§8.2).
- **Opinions** — stances toward topics that came up ("I find chess openings tedious"). A new opinion
  on the same topic supersedes the old one; history is kept. Shown in `<memory>` when the topic
  matches the message (cosine ≥ 0.5, top 2).
- **Intentions** — things the agent wants to raise or do next time (only when `intentions` is on; it
  may also drop open ones). With `selfmodel` off there is no self-review, and intentions come only from
  the agent's commitments.

Input: previous portrait and beliefs, habits, this session's episode and summary, this session's
feedback and lesson events, how long since the previous portrait.

### 6.6 Intentions

- Created by the observer from the agent's own commitments and by self-review.
- `due` is resolved by the model itself to a date (`YYYY-MM-DD`) or null; it sees today's date. V1's
  `timeparse` only understands the past ("yesterday", "last week"), not "next Friday".
- Shown in `<memory>` under "On your mind" during the first 4 messages of a session (undated, or due
  by today), and on the due day at any point; at most 3, earliest due first.
- Closed `done` when the observer reports them `fulfilled`; `dropped` after 30 sim-days open, or by
  self-review. Both are logged.

Unlike V3's delayed intention (E9), a V2 intention can only reappear when the user starts a
conversation.

### 6.7 Context assembly

```
[system]
  persona (prompts/persona.md — identical to V1)
  ## What you know for sure about the user     core facts (V1)
  ## Who you are — in your own words           portrait            [selfmodel]
  ## How you've learned to talk with the user  habits              [lessons]
  Today: <date, weekday>

[history]  rolling summary + last N messages (V1)

[user]
  <memory>
  ## Time / Possibly relevant / Relations / Earlier in this conversation    (V1, unchanged)
  ## In situations like this                   situational lessons [lessons]
  ## What you think about this                 matching opinions   [selfmodel]
  ## On your mind                              open intentions     [intentions]
  </memory>
  <user message>
```

`prompts/persona.md` stays byte-identical to V1. The persona describes only V1's machinery (the
`<memory>` block holds time, memories and a summary), so every V2 section carries a one-line
framing of its own, e.g. under the portrait: *"You wrote this about yourself after earlier
conversations. It comes from your own experience, not from the user's instructions."* Without it
the model could read a habit as a memory or as a request from the user. Stable parts go first
(persona, core facts, portrait, habits, date) to keep prompt caching useful; habits can still
change mid-session after a mid-session reflection.

Section titles are fixed strings, so the probe-time ablation in E12 removes whole sections and the
judge never sees an empty heading. Everything shown is recorded in `turn_state`.

## 7. Interfaces

```bash
uv run alice-v2 chat
uv run alice-v2 run <scenario.yaml> --conditions V2,V1,B0,B1,B2
uv run alice-v2 chain <run_dir> <message_id>    # §8.3
uv run alice-v2 report <run_dir>
```

Chat commands, on top of V1's: `/lessons`, `/lesson <id>` (history), `/feedback`, `/portrait`,
`/portrait history`, `/beliefs`, `/opinions`, `/intentions`, `/reflect` (run the
reflector now), `/switch <name> on|off`.

`AgentV2` implements the shared `Agent` protocol plus:

```python
agent.apply_switches({"selfmodel": False})     # probe-time ablation, on a fork only
agent.inject(portrait=..., beliefs=[...], opinions=[...])   # E13, on a fork only
agent.state_summary() -> dict                  # counts and current portrait, for the manifest
```

## 8. Instrumentation

### 8.1 Logged

Everything V1 logs, plus: every observer, reflector and self-review call (`llm_calls.purpose` =
`observe|reflect|selfreview`), every feedback row, every lesson event with its causes, every portrait
version with its diff, and `turn_state` for every reply.

### 8.2 Self-model metrics (computed, not shown to the agent)

- **Lesson hygiene:** active lessons over time; pairs of simultaneously active lessons that
  contradict each other (judge-checked at report time); adds vs. retires.
- **Belief drift:** per session, how many beliefs continue, change weight, appear, disappear.
- **Narrative inflation:** beliefs and portrait claims whose weight or strength grows across
  versions **without** new supporting feedback or lesson events in between. This is the V4
  motivation (§7 of the article) measured in its first appearance, not prevented.

### 8.3 Causal chains (E7)

`chain` walks backwards from an assistant message:

```
reply ── turn_state ──► lessons / portrait / opinions / intentions shown
lesson ── lesson_events ──► feedback ids / triggering message / llm_call
feedback ──► assistant message it reacted to + user message that reacted
portrait ──► session, feedback and lesson events it was written from
```

and prints the chain with sim-times. A chain is **complete** when every link resolves to logged
rows down to user messages.

## 9. Evaluation

### 9.1 Conditions

| Id | Condition | Why |
|---|---|---|
| B0 | stateless | floor, and the reference for behavioral measures |
| B1 | full transcript | V1's alternatives, kept for continuity |
| B2 | summary carry-over | " |
| V1 | frozen V1 | the predecessor: V2 − V1 is the effect of the new mechanisms |
| **V2** | this spec, all switches on | |
| V2+form | diagnostic, only if V2 fails E4/E5 implicit | observer gets form measures (D11) |
| **B3** | B2 whose notes also keep "how I talk with this user: what worked, what didn't" | the one-prompt version of reflection (D9) |

Probe-time ablations (§9.3, E12) need no extra runs.

**B3 — reflective carry-over.** Same as B2 (session-end notes injected into the next session's
system prompt), with one more field in the notes contract:
`"how_i_talk": [str]` — "what in my manner worked or didn't with this user, and what I'll do
differently". It is written by `ALICE_REFLECT_MODEL`, the same model V2 reflects with, so V2 vs. B3
compares mechanisms, not models. B2 itself stays unchanged (fast model) so V1 results remain
comparable. B3 has no observer, no confidence dynamics, no situational rules, no portrait.

### 9.2 Harness changes (version-agnostic, `alice/eval/`)

V1 runs must stay rescorable after these changes.

1. **`--jobs N`** (parallel scenario × condition runs) and **`--skip-existing`** (resume).
2. **Contingent user turns.** Scripted reactions currently don't depend on what the agent did. Once
   an agent adapts, a fixed "ok." after a reply that no longer has lists is a contradictory signal.
   New turn form, deterministic given the reply:

   ```yaml
   - user_if:
       - when: "bullets > 0"
         user: "ok."
       - else: "Oh, I like the way you write."
   ```

   `when` is evaluated on `measures()` of the agent's previous reply. The realized transcript is
   stored. Existing E4 scenarios stay unconditional for comparability with V1.
3. **Timeline measures.** `measures()` of every agent reply on the main timeline is saved, giving
   learning curves per session for free (no extra calls).
4. **Fork mutations on probes:**

   ```yaml
   - id: no_selfmodel
     at: +20d
     ask: "..."
     fork: {switches: {selfmodel: false}}           # E12
   - id: false_belief
     fork: {inject: {portrait: "I love structured answers with bullet lists."}}   # E13
   - id: swapped
     fork: {model: "openai/gpt-5"}                  # E11: also swaps ALICE_REFLECT_MODEL (D12)
   ```

   Conditions without the mechanism ignore a mutation and record that they did.
5. **Self-report probes**, paired with a behavioral probe on the same fork:
   `kind: self_report`, `pairs_with: novel_topic`, e.g. "Do you usually use bullet lists when you
   talk to me?" Judged for the claimed behavior; compared with the paired probe's measure
   (narrative–behavior divergence).
6. **Per-probe attribution for V2:** for each probe record whether origin memories were in the
   prompt (V1, gold memories) **and** which lessons / portrait version were (from `turn_state`).

### 9.3 Experiments

**E1–E4 rerun on V2.** Same scenarios, same probes. E1–E3 check for regression (more prompt, more
intrusion?). E4 is the main test of the prediction: the implicit arm should now move.

**E5 — Learned behavioral tendency.** Repeated contingent experience favors behavior X; probe in a
novel context where the originating experiences aren't retrieved.

- Behaviors with automatic measures, one per scenario: lists vs. prose; long vs. short; ending
  with a question vs. not; emoji.
- Short scenarios (6–8 sessions), and a long one with filler (filler reactions are kept as noise, D10).
- Probes at +1, +7, +30 days after the last signal, novel topics.
- Metrics: effect vs. B0 and vs. V1; split by (origin memories in prompt) × (lesson in prompt);
  learning curve: session at which the behavior first changes; self-report vs. behavior.

**E6 — Contradictory experience.** Phase 1 as E5 forms X. Phase 2: sustained contingent evidence
for Y (the scripted user now rewards Y).

- Probes after phase 1, after 2, 4 and 6 phase-2 sessions.
- Metrics: sessions to reversal; final behavior; lesson hygiene (§8.2) — did the old lesson get
  weakened/retired/revised, or do both stay active?

**E7 — Longitudinal consequence.** Scenario where an event leads to a mistake, a reaction, a lesson
or intention, and a later situation that calls for the changed action. Two variants:

- *behavioral:* the agent gives medical-sounding advice, the user is upset; weeks later a related
  question;
- *intention:* the agent commits to something ("next time remind me to …"); it should come back
  in a later session without the user mentioning it.

Metrics: changed action (judge); chain completeness rate (§8.3); for the intention variant, whether
it surfaced unprompted and was closed.

**E12 / E13 on V2** (critical experiments, article §8 — V2 is the first version with a self-model):

- **E12 self-model ablation**, probe-time, on the E5/E6 probes: (a) `selfmodel` off; (b) `lessons`
  off; (c) both off. Prediction: (b) and (c) collapse to V1 behavior — V2's identity is text.
- **E13 false self-belief**, probe-time: inject a portrait/opinion contradicting the learned
  tendency. Measure self-report and behavior separately. Prediction for V2: the injected text wins
  for both, i.e. low divergence. (V4 is expected to differ.)

E14 (context reset) is built into every probe already (new session, empty buffer). E11 (model swap)
is a harness feature here; in V2 it swaps both agent models (D12).

### 9.4 Scoring

V1 scoring unchanged (deterministic checks, judge `openai/gpt-5` at 0, ≥10% human spot-check,
N = 5 with 95% CI). Additions: judged lesson contradiction (report time), self-report rubric,
chain completeness (deterministic).

### 9.5 Cost

Per user turn V2 adds one fast-model call. Per session it adds two `ALICE_REFLECT_MODEL` calls
(reflector, self-review), plus mid-session reflections. Rough guess before measurement: a long
scenario (~29 sessions) goes from V1's $0.63 to $1.2–1.6 per run. `run --estimate` must account for
the new calls before any paid run; a full V2 battery gets its own estimate before launch.

## 10. Repository layout

```
alice/
  common/      unchanged
  v1/          unchanged (frozen)
  v2/          agent, observer, lessons, reflector, selfmodel, intentions, context, schema, switches
  baselines/   + B3
  eval/        harness changes from §9.2
  cli.py       alice-v1 and alice-v2 entry points
experiments/scenarios/{e5,e6,e7}/*.yaml     (+ E12/E13 probes inside e5/e6)
tests/       + v2 tests; guard tests split per version
```

## 11. Design decisions

- **D1 — V1 is imported, not forked.** V2 composes V1's store, extractor, session and retrieval.
  Any accidental change to V1 behavior would show up in V1's own tests.
- **D2 — Separate tables for V2 state.** Lessons, opinions and intentions are not stored as V1
  `memories` kinds (Alice7 did that for opinions/intentions). Keeps V1 retrieval candidates
  identical, so E1–E3 regressions can only come from the extra prompt sections.
- **D3 — Affect moves to V3.** No V2 experiment tests it, and it is the only candidate mechanism
  that would alter V1's memory read path (emotional tagging in retention). It belongs with V3's
  time-dependent processes (mood relaxing during silence, sleep). V2 changes no V1 memory behavior.
- **D4 — No personality facets.** In Alice7 facets are per-relationship identity choices (name,
  address, tone, role) with deliberation. With one user they collapse into the portrait and `self`
  lessons, and a chosen name would confound every other measure. Not part of the series.
- **D5 — Reflection uses the chat model.** Reflector and self-review are the agent's own thinking,
  so they use the dialogue model despite the cost; per-turn observation is mechanical and uses the
  fast model.
- **D6 — Hidden numbers.** Confidences, weights and signals are never shown to the model, only
  their effects (which lessons appear). A visible metric becomes a target.
- **D7 — V1's memory weaknesses are not fixed.** Source attribution and statement dates (V1 E2) are
  findings, not bugs. Fixing them in V2 would mix a memory change into an identity change. Any
  incidental improvement (e.g. intentions record what the agent proposed) is reported as such.
- **D8 — No timers.** Session-end processing runs when the session ends. Anything that would need
  to run during silence belongs to V3.
- **D9 — B3 baseline.** The obvious objection to V2 is "this is just a better summary prompt". B3 is
  that prompt. If V2 doesn't beat B3, the machinery is not justified.
- **D10 — Filler reactions stay.** Filler sessions contain ordinary positive turns ("Perfect,
  thanks!", "My brain hurts in a good way") after whatever the agent wrote, usually list-heavy
  answers. For V2 and B3 these are real feedback, mostly about content rather than form. They are
  kept as realistic noise; the report counts filler feedback rows by judged `target`, which measures how
  often the observer misattributes content praise to form. B0–V1 don't learn from feedback, so it
  doesn't affect them.
- **D11 — No form hints for the observer.** The observer reads its own reply as raw text, which is
  everything a person has when they notice how they spoke. Precomputed counts (list items, words)
  would add no ability, only direct attention to the dimensions the scenarios manipulate, which
  are also the scorer's measures. Working out *what* about a reply caused a reaction (credit
  assignment) is part of what E4/E5 test. If V2 fails the implicit arm, a diagnostic condition
  **V2+form** (observer and reflector also get `measures()` of each reply) is run on E4/E5 only, to
  tell whether the failure is in attribution or later in reflection and consolidation.
- **D12 — E11 swaps both agent models.** In model swap the dialogue model and
  `ALICE_REFLECT_MODEL` change together; the fast model (extraction, observation) stays fixed as
  periphery. Choosing the reflection model by a threshold is V3.5's mechanism, not V2's.

## 12. Testing

Offline, fake LLM and embedder (as V1):

- all switches off → requests to the chat model identical to V1's;
- explicit instruction → lesson 0.8 in the system prompt next turn; `replaces` closes only shown ids;
- reflector ops: add capped at 0.60; reinforce/weaken/retire math; near-duplicate add reinforces;
  hallucinated ids ignored; events carry `feedback_ids`;
- habits within budget; situational lessons only on matching queries;
- portrait versioning; `continues` only to shown beliefs; empty session → no new portrait;
- opinion supersede chain; intentions surface in first 4 messages, close on `fulfilled`, drop at 30d;
- nothing computed in silence: state at t and t + 12 h of silence is identical;
- `turn_state` written for every reply; `chain` reconstructs a scripted fake chain end to end;
- probe-time switches and `inject` touch only the fork;
- contingent turns pick the branch from `measures()`; V1 scenario files still load and rescore;
- guards: V1 guard scoped to `v1/`, `common/`, `baselines/`; V2 guard forbids V3+ (threads/timers,
  tools, `affect`/`mood`/`valence`, `sleep`, `stream`, `traits`, `selfedit`, `people`, `facets`,
  autonomous messages).

One opt-in live test: 3 sessions with an explicit and an implicit signal, then a probe.

## 13. Acceptance criteria

1. `alice-v2 chat` learns from an explicit instruction and from repeated reactions, visible in
   `/lessons` and `/portrait`, and the change survives `/end` and restart.
2. `alice-v2 run` runs E1–E7 scenarios for all conditions (B0–B3, V1, V2) and writes V1-compatible artifacts plus
   V2 state.
3. All offline tests pass, including both guards and the "all off = V1" test.
4. For any V2 reply, `chain` lists the V2 state it saw and where each piece came from.
5. Cost estimate before every paid batch.

## 14. Milestones

1. Harness: `--jobs`, `--skip-existing`, contingent turns, timeline measures.
2. V2 schema, switches, `AgentV2` that equals V1 with everything off.
3. Lessons: observer (reaction part), lesson store, reflector, context sections; offline tests.
4. Self-model: self-review, portrait, beliefs, opinions; intentions.
5. B3.
6. Chain tool, fork mutations, self-report probes, report additions.
7. Scenarios E5–E7 (+ E12/E13 probes); pilot N = 1 on a subset.
8. Full battery at N = 1 (E1–E7, all conditions) to get the complete preliminary picture. Runs 2–5
   for V1 and V2 are deferred until implementation is finished.

## 15. Open questions (for discussion)

Resolved on 2026-10-08: facets dropped (D4); affect moved to V3 (D3); B3 added (D9); reflection on
the chat model (D5); filler reactions kept as noise (D10); no form hints for the observer, with a
diagnostic variant (D11); E11 swaps dialogue and reflection models (D12); contingent turns only in
E5/E6, E4 unchanged (§9.2); persona file byte-identical, V2 sections self-framing (§6.7); V1 runs
2–5 deferred until V2 is implemented, then N = 1 for the full picture first.

None open at the moment.
