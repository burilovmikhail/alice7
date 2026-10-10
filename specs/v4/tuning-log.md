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
