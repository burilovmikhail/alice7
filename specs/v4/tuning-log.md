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
