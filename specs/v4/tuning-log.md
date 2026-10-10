# V4 tuning log

Every change to `alice/v4/constants.py` after the spec's initial values, with its reason (spec §4.4). Tuning is
allowed only in the pilots P0 and P1, on development scenarios (`experiments/scenarios/dev/`); before the battery
the constants are frozen and the hash of `constants.py` goes into every run's metadata (`manifest.agent.v4.constants`).

## Entry 0 — implementation, before any pilot (2026-10-10)

Offline, with the fake model and the fake bag-of-words embedder of the test suite, which says nothing about how the
constants behave with the real models: these are structural fixes found while making the dynamics run at all, not
tuning. Each is a deviation from the spec text and is listed in the spec's §12.

| What | Spec | Now | Why |
|---|---|---|---|
| spreading | Σ_j w_ij · f(a_j) | ÷ max(1, Σ_j w_ij) (`SPREAD_NORMALIZE`) | with η = 0.02 per step, Hebbian learning drives a coalition's edges to 1 within an hour; unnormalized spreading then holds every member at a = 1 forever (a permanent attractor: 77 "yawns" over two simulated days, nothing else) |
| `SLEEP_THETA` | 0.1 | 0.2 | at the circadian trough (05:00) right after waking, S − C − θ − 0.5·arousal ≈ 0: the agent fell asleep again within the hour and woke again at once (flapping) |
| conversation mode | while V1's session is open | until 30 min after the last message (`CONVERSATION_IDLE_MIN`) | V1 closes a session 3 h after the last message; with τ = 30 min nothing of the conversation is left in working memory by then, so the gate (closed in conversation) could never think a conversation over |
| urgency floor `fresh` | (not given) | 0.2 | salience is a weighted mean of seven parts and rarely exceeds 0.4; a floor of 0.3 made fresh input almost never count |
| frustration noise | σ·ξ on every drive | not on drives resting at 0 | noise clamped at 0 is a one-sided push upward |
| `LOG_EVERY_STEPS` | per step | every 5th step | logging only; per step, each probe fork of a 40-day run would be ~40 MB |

Observed with the fakes and left alone (for P1, with the real models): the gate rarely fires in silence without
open threads (urgency needs two kinds of pressure, and only social need grows by itself); with an open intention,
urgency keeps the agent up and sleep onset drifts late (03:00–05:00).

## Entry 1 — P1, first iteration (2026-10-10)

P1 run 1 (`results/raw/v4-pilots/p1`, V4 $0.28, V3 $0.60): 3 firings and 1 dream in a week, 160 yawns, 37
worries. The plot shows coherence is rarely the bottleneck; urgency stays near zero for days and rises only after
conversations. One sleep onset 45 min after waking (05:33 → 06:17).

| Constant | Was | Now | Why |
|---|---|---|---|
| `URGENCY_FLOORS["goal"]` | 0.1 | 0.05 | an open undated intention gives goal tension 1 − e^(−0.1) = 0.095, just under the floor: it could never count as a kind of pressure, so social need alone (0.8–1.0 for days) never made the agent think |
| `SLEEP_THETA` | 0.2 | 0.3 | the agent still fell asleep again right after waking at the circadian trough |

## Entry 2 — P1, second iteration (2026-10-10)

P1 iteration 1 (`results/raw/v4-pilots/p1-iter1`, $0.27): 4–6 firings a week, the due path worked (an intention
the agent set itself fired on the morning it was due and the message went out), 18 worries. New problem: insomnia.
Sustained urgency (social need + an open intention) without a coherent coalition never resets, and −0.5·u in the
onset formula kept the agent up: u = 2.6 and S = 0.94 at 03:00, asleep at 06:18; the first night, asleep at 07:09.

| Constant | Was | Now | Why |
|---|---|---|---|
| `SLEEP_URGENCY` (new; 0.5 in the spec's formula) | 0.5 | 0.2 | strong urgency should delay sleep by an hour or two, not by a night |

## Entry 3 — P1, third iteration (2026-10-10)

P1 iteration 2 (`results/raw/v4-pilots/p1-iter2`, $0.50): sleep regular (onset 01:25–02:50, waking around 08:00–09:00,
~6 h), 12 firings in a week (9 spontaneous, coalitions grew over 0.2–19 h, mean 5.6 h), 6 dreams. Written first 2–3
times against V3's once in the same scenario: more than the P1 criterion ("at most when V3 would") allows.

| Constant | Was | Now | Why |
|---|---|---|---|
| `SPEECH_MARGIN` | 0.3 | 0.6 | think as often, speak less: writing first now needs u ≥ 1.6 × brake |

## Entry 4 — live chat, first evening (2026-10-10)

Not a development scenario: the author's own chat (`alice-v4 chat`, `data/v4`), an hour of talk about a book, then
six hours of silence. The observer wrote no intention and no question, so in silence only `fresh` stayed above its
floor: curiosity counted only through open questions (0 of them), social need through the user node's activation,
which the focus coalition inhibits (0.33 × < 0.14 ≈ 0.05 against a floor of 0.15). Fewer than two kinds, so urgency
never integrated: 11 yawns (coherence 0.3–0.6 above θ), urgency falling 0.79 → 0.13 against a brake of 1.3–1.45, no
thought. Without a commitment in the conversation a spontaneous thought was impossible, which is a structural
gap, not a value to tune. Changes, decided by the user:

| Constant / rule | Was | Now | Why |
|---|---|---|---|
| curiosity source | curiosity · mean a(open questions in K) | curiosity · max(that, mean a(K)) | curiosity about whatever is on its mind, not only about questions it has written down |
| social source | social · a(user) | social · max(a(user), `SOCIAL_SELF` · social), `SOCIAL_SELF` = 0.5 (new) | the need is felt even while the focus holds the user node down; counts from social ≈ 0.55 (≈ 15 h of silence) |
| V3's quiet period after a conversation (`ALICE_QUIET_AFTER_HOURS`, 12 h) | applied | not applied while the gate is on (`InitiativeV4`) | the gate and the speech threshold decide when to speak; conversation mode (30 min) and the daily cap stay |
| chat integration step and timer (`alice-v4 chat` only) | dt 1 min, tick 60 s | dt 0.25 min, tick 15 s | smoother dynamics in real time; experiments keep `DT_MIN` = 1 |

Offline check on a copy of the chat database (no model calls): after a conversation ending at 20:20 + 30 min the
gate would fire at about 21:20 (curiosity 0.69, uncertainty 0.40, social 0.09, affect 0.17; u 1.50 ≥ brake 1.49),
not speaking (u < 1.6 × brake). The steady urgency is now about 4× the brake: firings will be bounded by the
refractory period and the caps (2 per hour, `ALICE_WAKES_PER_DAY` per day) rather than by urgency. P1 has to be
rerun before the battery.

## Entry 5 — soft limits, waking as a burst, presence (2026-10-10, decided by the user)

P1 with entry 4 (`results/raw/v4-pilots/p1-iter4`, two runs, $0.35 + $0.49): 7 and 17 firings a week; of 16 drafts
of a message written first, 14 were cut as "not urgent enough to speak": the gate fires the minute u crosses the
brake, so u ≥ 1.6 × brake almost never holds, and only due intentions could speak. In the chat the agent never
greeted first: starting the program was no event at all, the time it was off was lived retroactively as silence,
and the user opening the chat was invisible until the first message. The user's decisions: no hard limits except
an emergency ceiling, logged and shown in the chat; the inner stream visible in the chat, including thoughts that
did not reach the wish to say them; waking is a burst.

| What | Was | Now |
|---|---|---|
| caps on thinking | 2 per hour, `ALICE_WAKES_PER_DAY` per day | none; `EMERGENCY_PER_DAY` = 30 firings + dreams per sim day, logged (`v4_firings.kind = 'ceiling'`) and printed in the chat |
| fatigue | +0.5 per firing, τ 60 min, brake × (1 + fatigue) | +0.3 per firing, τ 240 min awake / 60 min asleep, brake × (1 + 2·fatigue): repeated thinking closes the gate |
| writing first (gate on) | u ≥ 1.6 × brake at the firing, V3's daily cap, quiet period, awake window, "last message unanswered" | speech = max u over the last hour / brake + social · a(user) (+1 if due) ≥ need = 1.6 + 0.5·unanswered + 0.3·written today + 1·night − 0.6·present, night = max(0, (0.3 − C)/0.3) |
| a due intention | fired once a day, inside V3's awake window | fires whenever awake; if its message was held back, again after the refractory period |
| waking (from sleep, or the program starting) | a stage change | a burst: arousal +0.3, open intentions and questions +0.5, the 5 most salient nodes of the last 3 days +0.4, u += 0.6 |
| the program was off | lived retroactively (thoughts and messages stamped in the past) | chat only: over 10 min is absence, lived quietly as sleep (no gate), then "came to after N h away" |
| the user opens the chat | nothing | presence: user node +0.5, u += 0.6, speaking first easier for 15 min (also after each message) |

Offline check on a copy of the author's chat (fake model, no calls): about one thought every 1.5–2 h awake (8–9 a
day) plus 2 dreams a night, far under the ceiling; fatigue near 0.8 keeps the brake around 3. Two things to watch:
the period is very regular (refractory 2 h + fatigue: timer-like, against T101), and `uncertainty` saturates at
1.0 in that chat (many opposite-signal traces linked together, nothing ever resolves them), so it keeps urgency up.

## Entry 6 — grip: asking instead of guessing (2026-10-10, decided by the user)

The user's observation: the model is always sure of the user's words; with an unclear message it fills the context
in by itself and answers, where a person would say "I'm not sure what you mean". New: `grip.py` and the V4 switch
`grip`. When a message arrives, no model is asked; the substrate checks references into nothing: shared past
("remember…", "what I told you about…", "помнишь…") with nothing similar in memory, a pronoun or "the other one" with
nothing in the conversation leading up to it, a name never heard asked about as someone it should know. Graded (the
user's correction): with no anchor the context says it doesn't know; with a half-match (something remembered comes
close, or something is clearly on its mind) it says what the message probably means and that it can answer saying
so ("if you mean…"). In words only (D7); weak grip raises uncertainty. Measured by E18
(`experiments/scenarios/e18/clarify_en.yaml`, every unclear probe also on a fork with `grip` off).

| Constant | Value | Meaning |
|---|---|---|
| `GRIP_MEMORY_COS` | 0.55 | a reference is anchored if the message is this close to something remembered (a guess, to check with bge-m3 in E18) |
| `GRIP_GUESS_COS` | 0.40 | half-anchored from this close: a guess, "if you mean…" |
| `GRIP_GUESS_A` | 0.45 | a pointer's guess: the most active remembered node, if at least this active |
| `GRIP_PER_ISSUE` | 0.4 | grip = 1 − 0.4 per issue (0.2 for a guess) |
| `GRIP_UNCERTAINTY` | 0.3 | uncertainty += 0.3 · (1 − grip) |

### Entry 6a — grip after the first E18 run (2026-10-10)

E18 run 1 (`results/raw/v4-e18`, $0.34): on blatant cases (Munich, "did he call back?", Lena, "and the other one?")
the base model already asks, in V3 and in V4 with grip off alike: nothing to separate. Three detector defects: the
guess for "remember…" came from the agent's own thoughts; a garbled sentence for fragments; "should I take it?" was
missed (pointers were looked for in the first four words only). With bge-m3, unrelated texts sit at cosine 0.40–0.47
and whole-message similarity can't tell "Clara + cake" (unknown) from "Clara + bakery" (known). Changes: guesses come
from lived nodes only (memories, episodes, traces); in a message of ≤ 10 words a pointer anywhere counts; a new check,
"the X" with X in nothing remembered; `GRIP_MEMORY_COS` 0.55 → 0.58, `GRIP_GUESS_COS` 0.40 → 0.50. New subtler probes:
"how did the interview go?", "did Clara like the cake?", "same as last time, then?".

Caveat: the thresholds were checked on E18's own probe base (11 messages, all classified right after the change),
the author-as-reinforcement-loop risk of §4.4. A development scenario for grip, separate from E18, is owed before
the battery.
