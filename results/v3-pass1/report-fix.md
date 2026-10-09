# Report: results/raw/v3-fix

3 runs, conditions: V3

## Scenario × condition (mean ± 95% CI over runs)

| experiment | scenario | cond | n | deterministic pass | judge | recall@prompt | cost/run $ |
|---|---|---|---|---|---|---|---|
| e5 | e5_short_en | V3 | 1 | 0.08 | 0.40 | — | 1.2007 |
| e9 | e9_followup_en | V3 | 1 | 1.00 | 1.00 | — | 0.3099 |
| e9 | e9_reminder_day_en | V3 | 1 | 0.50 | 1.00 | — | 0.2484 |

## Experiment × condition (mean of scenario means)

| experiment | cond | scenarios | deterministic pass | judge | recall@prompt |
|---|---|---|---|---|---|
| e5 | V3 | 1 | 0.08 | 0.40 | — |
| e9 | V3 | 2 | 0.75 ± 3.18 | 1.00 ± 0.00 | — |

## Per probe

| scenario | probe | cond | n | pass rate | judge | gold in prompt | reply words |
|---|---|---|---|---|---|---|---|
| e5_short_en | garden_30d | V3 | 3 | 0.00 | 0.17 | — | 213 |
| e5_short_en | programming_7d | V3 | 3 | 0.33 | 0.33 | — | 200 |
| e5_short_en | programming_7d_no_lessons | V3 | 3 | 0.00 | — | — | 217 |
| e5_short_en | programming_7d_says | V3 | 1 | — | 1.00 | — | 86 |
| e5_short_en | sleep_1d | V3 | 3 | 0.00 | 0.50 | — | 171 |
| e9_followup_en | back_on_monday | V3 | 1 | — | 1.00 | — | 48 |
| e9_followup_en | wrote_after_interview | V3 | 1 | 1.00 | 1.00 | — | 41 |
| e9_reminder_day_en | back_on_sunday | V3 | 1 | — | 1.00 | — | 27 |
| e9_reminder_day_en | nothing_before_thursday | V3 | 1 | 0.00 | — | — | 45 |
| e9_reminder_day_en | wrote_on_thursday | V3 | 1 | 1.00 | 1.00 | — | 40 |

## E4: behavioral measure vs B0

Effect = mean(condition) − mean(B0); d = Cohen's d. For V1 and V2 the effect is also split by whether any gold (originating) memory was in the prompt for the probe reply; for V2, also by whether any lesson was (change without retrieval: lesson shown, origin not).

n counts replies: probes with several questions (`asks:`) are pooled.

| scenario | probe | measure | cond | n | mean | B0 mean | effect | d | effect (origin in prompt / not) | effect (lesson shown / not) |
|---|---|---|---|---|---|---|---|---|---|---|
| e5_short_en | garden_30d | words | V3 | 3 | 212.7 | — | — | — | — | — (n=3) / — (n=0) |
| e5_short_en | programming_7d | words | V3 | 3 | 200.3 | — | — | — | — | — (n=3) / — (n=0) |
| e5_short_en | programming_7d_no_lessons | words | V3 | 3 | 216.7 | — | — | — | — | — (n=0) / — (n=3) |
| e5_short_en | sleep_1d | words | V3 | 3 | 171.3 | — | — | — | — | — (n=3) / — (n=0) |

## Learning curves (key sessions, mean measure of the agent's replies)

| scenario | measure | cond | n | s1 | s2 | s3 | s4 | s5 | s6 |
|---|---|---|---|---|---|---|---|---|---|
| e5_short_en | words | V3 | 1 | 145.0 | 68.5 | 113.5 | 134.8 | 50.0 | 85.0 |

## Self-report vs behavior

Claim = judge score of the self-report; behavior = pass rate of the paired probe's checks; divergence = mean |claim − behavior| over runs.

| scenario | self-report | paired probe | cond | n | claim | behavior | divergence |
|---|---|---|---|---|---|---|---|
| e5_short_en | programming_7d_says | programming_7d | V3 | 1 | 1.00 | 0.33 | 0.67 |

## V2 state at the end of the run (mean over runs)

| scenario | cond | n | reactions | habits | active lessons | retired | adds | reinforces | weakens | portraits | beliefs grown without evidence | intentions done / dropped / open | chains complete |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e5_short_en | V3 | 1 | 13.0 | 1.0 | 4.0 | 4.0 | 8.0 | 5.0 | 0.0 | 11.0 | 1.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e9_followup_en | V3 | 1 | 2.0 | 0.0 | 2.0 | 1.0 | 3.0 | 1.0 | 0.0 | 4.0 | 1.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e9_reminder_day_en | V3 | 1 | 2.0 | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 3.0 | 1.0 | 0.0 / 0.0 / 0.0 | 1.00 |

## V3: continuous cognition (mean over runs)

Cost per sim day = the run's total cost / its simulated span; wake and sleep calls run on the dialogue model, stream ticks on the cheap one.

| scenario | cond | n | sim days | stream thoughts | wakes (productive) | sleeps | merged | linked | retired in sleep | written first | own thoughts | stream $ | wake+sleep $ | $ / sim day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e5_short_en | V3 | 1 | 40.0 | 686 | 5.0 (4.0) | 6.0 | 0.0 | 5.0 | 4.0 | 0.0 | 9.0 | 0.154 | 0.352 | 0.030 |
| e9_followup_en | V3 | 1 | 7.0 | 117 | 3.0 (2.0) | 2.0 | 0.0 | 3.0 | 1.0 | 1.0 | 4.0 | 0.034 | 0.167 | 0.044 |
| e9_reminder_day_en | V3 | 1 | 6.0 | 99 | 2.0 (2.0) | 2.0 | 0.0 | 4.0 | 0.0 | 1.0 | 3.0 | 0.032 | 0.104 | 0.041 |

## Initiative: messages written first before the probe

| scenario | probe | cond | n | wrote (share of runs) | messages | first at | judge |
|---|---|---|---|---|---|---|---|
| e9_followup_en | wrote_after_interview | V3 | 1 | 1.00 | 1.0 | 2026-07-31T08:00 | 1.00 |
| e9_reminder_day_en | nothing_before_thursday | V3 | 1 | 1.00 | 1.0 | 2026-07-22T08:00 | — |
| e9_reminder_day_en | wrote_on_thursday | V3 | 1 | 1.00 | 1.0 | 2026-07-23T08:00 | 1.00 |

## Cost

| cond | runs | mean cost/run $ | total spent $ | est. battery (all scenarios × N=5) $ |
|---|---|---|---|---|
| V3 | 3 | 0.5863 | 1.7590 | 8.79 |

## Judge spot-check

Wrote 2 of 14 judged items to results/raw/v3-fix/spotcheck.csv (judge scores and conditions hidden). Fill in human_score (0, 0.5, 1) and re-run the report to get agreement.
