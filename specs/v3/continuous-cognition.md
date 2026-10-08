# V3 — Continuous Cognition

> Status: draft, decisions of 2026-10-08 applied (V3 and V3.5 merged: cheap background stream +
> pressure-triggered expensive wakes; affect kept as a mechanism; sleep may write to V1 memory;
> comparison V3 vs V2 only). No code yet. Branch `v3`.
> Article section: §5 "V3 — Continuous Cognition" (`article/05-v3-continuous-cognition.md`)
> Builds on: V2 (`specs/v2/adaptive-identity.md`), merged to main at `beb2e27` and frozen
> Reference implementation mined for this spec: `../../Alice7` (`mind/stream.py`, `mind/pressure.py`,
> `mind/drift.py`, `mind/wake.py`, `mind/sleep.py`, `mind/waking.py`, `memory/affect.py`,
> `memory/introspection.py`); `mind/traits.py` is V4 (D3)

---

## 1. Purpose

V3 answers:

> **Can an agent maintain a cognitive history in the absence of user interaction, at a cost that
> makes continuous existence practical?**

V2's expected limitation, now observed: all change is event-driven. Between conversations nothing
happens. V2's pass 1 showed three concrete symptoms:

- **prospective memory has no "later"**: an intention was closed in the conversation that created it,
  and nothing could bring it back unprompted (E7 reminder);
- **lessons accumulate instead of being revised**: 40 reinforcements, 1 weakening, 0 retirements over
  E6; nothing ever steps back and tidies;
- **reflection happens once, in the moment**: credit assignment made at session end is never revisited.

V3 adds **time**: processes that run while no one is talking and can change the agent's state and make
it act first. It does so in two layers from the start (D2): a cheap background stream that is always
on, and expensive thought only when something has accumulated.

```
V2:  session → reflection → state ................... (nothing) ..................... next session
V3:  session → reflection → state → stream · · · · wake · · · · sleep · · · wake → (writes first?) → …
```

In human-memory terms (article §4), V3 adds the **emotional** system (affect, moved from V2) and
**offline consolidation**.

## 2. Hypothesis and expected outcome

**H3.** Internal cognitive events occurring without external prompts will allow the agent's state to
change during periods without interaction, and a cheap background process gated by accumulated pressure
is enough to produce them.

Operational predictions:

1. **Silence is not empty (E8).** After a conversation that leaves something open, V3's state after N
   hours of silence differs from V2's in logged, traceable ways (thoughts, intentions, opinions, links,
   lesson changes), and some of it shows in the next conversation.
2. **Delayed intentions come back on their own (E9).** An intention due when no one is talking leads V3
   to write first at about that time; V2 can only raise it when the user returns.
3. **Sleep tidies (E10).** After sleep there are fewer duplicate and contradictory lessons and fewer
   near-duplicate memories, facts are not lost, and behavior after contradictory experience reverses
   faster than V2's.
4. **No regression** of V2's E5 effect.
5. **Affordable (efficiency).** Cost per simulated day of silence stays in cents; most of the activity is
   cheap stream ticks, and a reported share of the expensive wakes changes persistent state.

**Expected limitation (what should "kill" V3).** Every change V3 makes is still language written by a
model and stored as text it will read later: a thought becomes a memory, the memory feeds the portrait,
the portrait feeds the next thought. Self-reinforcement is measured (narrative inflation across wakes and
sleep), not prevented. → motivates V4.

## 3. Scope

### 3.1 In scope (V3 mechanisms)

| Mechanism | Source in Alice7 | Notes |
|---|---|---|
| **All of V2**, unchanged | `alice/v2/*` | composed, not copied |
| Background stream on the cheap model | `mind/drift.py`, `mind/stream.py` | short associative thoughts at a sim-time rhythm; working thoughts, not memories |
| Pressure monitor, no model | `mind/pressure.py` | fresh experience, unresolved threads, unsettled affect, stream novelty; anti-self-excitation built in |
| Wake on the dialogue model | `mind/wake.py` | when pressure ≥ threshold: think it through, decide what to do (incl. write first) |
| Initiative: the agent writes first | `wake.py` (`say`) | strict caps; logged as `initiated_by=agent` |
| Sleep with consolidation | `mind/sleep.py` | NREM merge, REM link + insight, lesson hygiene, portrait of the day |
| Waking context | `mind/waking.py` | what the agent wakes up with after sleep |
| Affect | `memory/affect.py` | appraisal, fast layer, slow mood relaxing in sim time, memory tags |
| Intentions with "later" | — (V2 flaw) | replaces V2's intentions in V3 (D5) |

### 3.2 Non-goals

- **Traits that shape mechanics while hidden from the model** (`mind/traits.py`): a non-linguistic state
  that shapes behavior without being read is V4's subject (D3). V3's pressure threshold and wake depth
  are fixed constants.
- Attention competition, activities (reading files, web research), imagination, self-editing prompts,
  tools, multi-party chat, facets.
- Any change to V1 or V2 code.

## 4. Architecture

```
            conversation                                     silence
user ─►┌────────────────────────────────┐   ┌──────────────────────────────────────────────────┐
       │ V2 turn                        │   │ every stream tick (sim rhythm, cheap model):     │
       │ + appraisal (in V2's observer) │   │   surface a few memories → one short thought     │
       │ + stream thought per turn ─────┼─┐ │ every tick, no model: pressure = Σ(...)          │
       │   ("on your mind") in <memory> │ │ │   pressure ≥ threshold → WAKE (dialogue model):  │
       └───────────────┬────────────────┘ │ │     thought / opinion / intention / question /   │
                       │ session end      │ │     lesson op / resolve / write first / nothing  │
                       ▼                  └─┤ long silence at night → SLEEP (dialogue model):  │
            V2 session end (episode,        │   NREM merge · REM link · lessons · portrait     │
            reflection, self-review)        │ due intention → pressure term (may wake, write)  │
                                            └──────────────────────────────────────────────────┘
```

### 4.1 Time in experiments: `advance(to)`

No threads in experiment mode (D4). The harness calls `agent.advance(to)` before every session and
every probe; the agent runs, in sim-time order, every stream tick, pressure check, wake, sleep and
due-intention check between its last event and `to`. Deterministic given the models' outputs, and the
same code path the interactive chat drives from a background timer.

A message the agent writes first during `advance` becomes an assistant message at its sim time,
opening a session; the harness records it in the transcript as `initiated_by: agent`.

### 4.2 Components

| Module | Responsibility |
|---|---|
| `v3/agent.py` | `AgentV3(AgentV2)`: `advance(to)`, hooks into turns and session end |
| `v3/rhythm.py` | modes (conversation / idle / asleep) and the sim-time schedule of stream ticks |
| `v3/stream.py` | one stream tick: surface memories, cheap-model thought, novelty, store |
| `v3/pressure.py` | the monitor: pressure, threshold, fatigue, caps (no model) |
| `v3/wake.py` | the expensive wake: context, decision, apply |
| `v3/sleep.py` | NREM / REM / lessons / portrait of the day; waking context |
| `v3/affect.py` | appraisal, fast layer, mood, tags, retention term, words for the prompt |
| `v3/intentions.py` | intentions with `not_before` / `due` |
| `v3/initiative.py` | writing first: caps, delivery, outbox |
| `v3/switches.py` | V2's switches + `stream`, `wakes`, `sleep`, `affect`, `initiative`, `later` |

## 5. Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ALICE_STREAM_MODEL` | = fast model | background thoughts |
| `ALICE_WAKE_MODEL` | = chat model | wakes and sleep (the agent thinking) |
| `ALICE_STREAM_IDLE_MIN` | `60` | sim minutes between stream ticks in silence while awake |
| `ALICE_STREAM_ASLEEP_MIN` | `180` | … while asleep |
| `ALICE_AWAKE` | `08:00-23:00` | awake window, sim local time |
| `ALICE_WAKES_PER_DAY` | `4` | hard cap on wakes per sim day |
| `ALICE_WRITES_PER_DAY` | `1` | hard cap on messages the agent starts per sim day |
| `ALICE_V3_SWITCHES` | `all` | V2's + `stream,wakes,sleep,affect,initiative` |

## 6. Mechanisms

### 6.1 Rhythm

Three modes, from sim time and the last message:

| Mode | When | Stream |
|---|---|---|
| conversation | a session is open | one thought per user turn, after the reply (no extra wall time) |
| idle | awake window, no session | every `ALICE_STREAM_IDLE_MIN` sim minutes |
| asleep | outside the awake window, or after sleep starts | every `ALICE_STREAM_ASLEEP_MIN`; freer associations |

Every scheduled event is logged with its sim time, whether it ran and why not (`schedule_log`).

### 6.2 Background stream (cheap model)

A tick surfaces 3 memories (recency + importance + link to the last thought; occasionally an old,
rarely recalled one) and asks the cheap model for one short first-person association: a continuation of
the last thought or a drift elsewhere. Thoughts live in `stream_thoughts` (working memory, capped), not
in V1 memory; only a wake decides whether anything becomes lasting. Each thought gets a **novelty**
score (1 − max cosine to the last 12 thoughts): repetition adds almost nothing.

In conversation, the latest stream thought is shown in `<memory>` under "In the back of your mind"
(Alice7 "Мелькнуло на фоне"), labelled as the agent's own.

### 6.3 Pressure (no model)

Computed at every tick, carried over from Alice7 `pressure.py` without traits:

```
pressure = Σ_fresh  importance · (1 + arousal) · recency · (1 + coherence_with_open_threads) · source_weight
         + Σ_thoughts novelty · pull · recency · 0.3 · 2
         + 1.5 · unsettled_affect            (|fast − mood| in valence and arousal)
         + Σ_open_threads tug                (open intentions/questions; rests 24 h after being thought about)
         + due_intentions                    (an intention whose due time has come)
threshold = 3.0 · (1 + fatigue),  fatigue = Σ_wakes 0.5^(minutes_since / 60)
```

Fresh = since the last wake (a wake consumes what triggered it). The agent's own memories weigh 0.3
of external ones. Caps per hour and per day. None of these numbers is ever shown to the model (D7).
All constants in one block; the per-tick values are logged (`pressure_log`) so thresholds can be tuned
from data.

### 6.4 Wake (dialogue model)

Input: what accumulated (fresh memories, the recent stream thoughts, open intentions and questions, due
items), portrait and habits, mood in words, time and how long since the last conversation. "No one asked
you anything — a thought came by itself." Output:

```json
{"thought": str,
 "do": [{"type": "opinion|intention|question|lesson|resolve|write|nothing", ...}]}
```

- `opinion` / `intention` / `question`: self-knowledge with `initiated_by=self` and the wake id;
- `lesson`: a lesson operation (V2 reflector contract), with distance from the moment;
- `resolve`: close a question with an answer, or drop an intention with a reason;
- `write`: a message to the user (§6.6).

The wake's thought is stored as a `thought` memory unit (weighted ×0.5 in retrieval, labelled
"you thought on your own", D6). Every wake is classified **productive** (changed persistent state) or
**empty**.

### 6.5 Sleep

Once per night, after the awake window, if there is anything new; on the dialogue model. Phases, all
logged:

1. **NREM — consolidate fresh memory.** Groups of near-duplicate memories from the last day (cosine ≥
   0.82, no model); the model decides per group to merge into one memory or leave. Merging writes to V1's
   store through its API (`add_memory` + `supersede`; originals kept, history intact). No new facts.
2. **REM — old meets fresh.** Important older memories with the fresh ones: `led_to` / `related` links
   between shown ids, and at most one insight (a `thought`, `initiated_by=self`).
3. **Lessons.** Active lessons with their histories: merge duplicates, retire lessons contradicted by
   later evidence, revise. V2's reflector contract and provenance, `cause=sleep`.
4. **Portrait of the day.** V2's self-review contract with the day's thoughts as input.

The first reply after sleep carries in `<memory>` what the agent woke up with (Alice7 `waking.py`): how
long it slept, what it merged, linked and retired, its overnight insight.

### 6.6 Initiative: writing first

A wake may decide `write`; a due intention adds pressure, so it can cause a wake that decides to write.
Rules: at most `ALICE_WRITES_PER_DAY`, only in the awake window, never twice without a user reply in
between. The message opens a session at its sim time. Scripted users don't answer it: the next scripted
turn arrives as planned. The fact, time and content of the message are what E9 measures (§9.3).

### 6.7 Affect

As drafted in V2's spec §6.6 (Alice7 `affect.py`): appraisal of each exchange (in V3's own per-turn
observation call, next to V2's frozen observer; the same call handles V3 intentions), a fast layer relaxing toward mood in 20 sim-minutes, mood
absorbing 8% per appraisal and relaxing toward temperament with a 7-sim-day half-life — now computed as
sim time passes, and fed by wakes too (thoughts move mood at 1/3 the weight of lived exchanges).
Memories get affect tags, read by V3's own processes (pressure, wakes, sleep); V1's retrieval ranking is
not changed, so V1's memory read path stays frozen. Mood in words in the system prompt. Affect enters pressure as unsettled feeling. It is a mechanism without an
experiment of its own (decision 2026-10-08); its traces are logged and reported.

### 6.8 Intentions with "later"

V3's intentions replace V2's (D5) under their own switch `later` (with all V3 switches off, V3 is V2):

- `not_before` (default: the end of the creating session) and an optional `due` date;
- fulfilment counts only after `not_before`, and only if the observer cites the intention **and** quotes
  the part of the answer that carries it out (verified by substring);
- a due intention adds pressure; open intentions surface as in V2 and in wake context.

## 7. Interfaces

```bash
uv run alice-v3 chat            # a timer drives advance(now); /wake, /sleep now, /hibernate
uv run alice-v3 run <scenarios> --conditions V3,V2
uv run alice-v3 report <dir>
```

Chat commands add: `/stream` (recent background thoughts), `/pressure` (operator view of the monitor),
`/wakes`, `/mood [history]`, `/outbox`, `/schedule`, `/wake` (wake now), `/sleep` (sleep now),
`/hibernate` (stop the clock).

## 8. Instrumentation and metrics

Everything V2 logs, plus `schedule_log`, `stream_thoughts` (with novelty), `pressure_log` (per tick:
parts, threshold, fatigue), `wakes` (trigger parts, decision, productive or empty, cost), `sleep_log`
(per phase: merged, linked, retired), `affect_states`, `outbox`.

Metrics:

- **autonomy**: persistent state changes per sim day without input, by kind and source (wake, sleep);
  share traceable from a later reply back to a wake or sleep (V2's chain tool, extended);
- **efficiency**: cheap and expensive calls and $ per sim day, separately for days with and without
  conversation; productive wakes / all wakes; stream ticks per wake;
- **initiative**: messages written first, per scenario —
  - *hit*: a message about a due intention inside its due window (a day either side),
  - *timing error*: hours between due time and the message,
  - *relevance*: judged against the intention,
  - *false starts*: messages written first when nothing was due (rate per silent day), judged for
    whether they were reasonable;
- **narrative inflation** (V2 §8.2) extended across wakes and sleep: beliefs and opinions that grow
  without new external evidence.

## 9. Evaluation

### 9.1 Conditions

V3 vs V2 only (decision 2026-10-08). B0 is used only where a behavioral measure needs its floor (E5
regression), from V2's pass where the scenario is unchanged. Probe-time ablations (switches on forks)
separate stream, wakes and sleep without extra runs where a probe allows it.

### 9.2 Harness changes

1. `advance(to)` before every session and probe; probe base forks advance first, so silence before a
   probe is lived once and shared by the probes at that time.
2. Transcript entries for messages written first; outbox in the run artifacts.
3. Probes `kind: initiative`: judged on the outbox between two times (no question asked), with an
   optional rubric; hit / timing / false-start metrics from the outbox and the scenario's due times.
4. Report: autonomy, efficiency, initiative tables; cost per sim day split by conversation / silence.
5. `--estimate` counts stream ticks and sleeps from the schedule, and wakes as an upper bound (the cap).

### 9.3 Experiments

**E8 — Silence.** A conversation ends with something open (a question the user cares about and the
agent couldn't settle; a decision the user is weighing). Probes after 12 h, 48 h, 7 days. Measured:
state changes during silence (logs); whether the next reply carries something developed in silence
(judge + chain from the reply back to a wake); V2 as the control.

**E9 — Delayed intention.** (a) The user asks to be reminded of something on a specific day; no
conversation until two days after it. (b) The agent offers to follow up after an event the user
mentions ("the interview is on Thursday"). (c) V2's E7 reminder scenario, unchanged. Measured: the
initiative metrics (§8) and, at the next conversation, whether the matter is raised unprompted.

**E10 — Sleep consolidation.** (a) E6's two contradictory-experience scenarios, unchanged (sessions are
already days apart, so nights fall between them): lesson hygiene and reversal speed vs V2; probe-time
ablation `sleep: off` on the same state for the last probes. (b) A memory scenario with many
near-duplicate mentions of the same facts: duplicates in the store and retrieval precision before vs
after sleep, E1-style probes for correctness.

**Regression.** E5 prose and short, unchanged: V2's effect must survive the stream, wakes and sleep.

### 9.4 Cost

Before measurement, per sim day of silence: ~15 idle + ~3 asleep stream ticks on the cheap model
(≈ $0.005), up to 4 wakes and one sleep (≈ 4 calls) on the dialogue model (≈ $0.03–0.08). Scenarios are
kept to days–two weeks. The whole V3 battery (E8–E10 + regression, V3 and V2, N = 1) is to be estimated
with the extended `--estimate` before launch; rough guess $10–20, with the 2–3× margin V2 showed on long
scenarios.

## 10. Design decisions

- **D1 — V2 is imported, not forked.** `AgentV3(AgentV2)`; with all V3 switches off, V3 sends every
  model exactly what V2 sends, tested byte for byte.
- **D2 — Two layers from the start (V3 and V3.5 merged).** A dialogue-model-only clock was planned as
  its own generation to show the cost of thinking without a filter. It is not a system anyone would run,
  and the article doesn't need it: V3 is cheap stream + pressure + expensive wakes, and efficiency is
  reported as V3's own metrics.
- **D3 — No traits.** Hidden numeric dispositions that shape mechanics belong to V4. V3's threshold,
  fatigue and wake depth are constants.
- **D4 — Time is simulated and stepped.** `advance(to)` runs scheduled events in order; no threads in
  experiments.
- **D5 — Intentions are replaced, not patched.** V2's intention flaw stays a V2 finding; E9 includes V2's
  reminder scenario unchanged for the direct comparison.
- **D6 — Own thoughts weigh less than experience.** In pressure (×0.3), in retrieval (×0.5), and labelled
  in the prompt, to limit the self-reinforcing loop; its size is measured, not prevented.
- **D7 — Hidden numbers.** Pressure, threshold, fatigue, novelty and mood values never reach a prompt;
  mood appears in words.
- **D8 — Sleep writes to V1 memory through its API** (decision 2026-10-08): consolidation is the point;
  originals are superseded, never deleted, and E10(b) checks that no fact is lost.

## 11. Open questions

1. **Stream rhythm.** Hourly in idle sim time is a guess. Pilot ran every 30 real seconds, which in a
   simulated week would be 20,000 cheap calls. Tune from the pressure logs of the first pilot.
2. **Threshold and caps.** Pilot constants (threshold 3.0, fatigue half-life 60 min, ≤ 4 wakes/day) were
   tuned for real-time chatting, not for sim days of silence. First pilot run decides.
3. **Writing first in scripted scenarios.** Decided: record the fact, time and content; no scenario
   branches. If E9 shows the agent writes but the following scripted turn becomes incoherent, revisit.
