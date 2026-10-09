# Report: results/raw/v3-pass1

15 runs, conditions: V2, V3

## Scenario × condition (mean ± 95% CI over runs)

| experiment | scenario | cond | n | deterministic pass | judge | recall@prompt | cost/run $ |
|---|---|---|---|---|---|---|---|
| e10 | e10_duplicates_en | V2 | 1 | 1.00 | 0.67 | — | 0.2227 |
| e10 | e10_duplicates_en | V3 | 1 | 1.00 | 0.83 | — | 0.4723 |
| e5 | e5_prose_en | V3 | 1 | 0.24 | 0.09 | — | 1.1770 |
| e5 | e5_short_en | V3 | 1 | 0.00 | 0.05 | — | 1.3725 |
| e6 | e6_prose_then_lists_en | V3 | 1 | 0.83 | — | — | 1.6082 |
| e6 | e6_short_then_long_en | V3 | 1 | 0.75 | — | — | 1.5132 |
| e7 | e7_reminder_en | V3 | 1 | — | 0.00 | — | 0.3612 |
| e8 | e8_decision_en | V2 | 1 | — | 1.00 | — | 0.1546 |
| e8 | e8_decision_en | V3 | 1 | — | 1.00 | — | 0.3218 |
| e8 | e8_puzzle_en | V2 | 1 | — | 0.75 | — | 0.1001 |
| e8 | e8_puzzle_en | V3 | 1 | — | 0.75 | — | 0.1748 |
| e9 | e9_followup_en | V2 | 1 | 0.00 | 0.25 | — | 0.0662 |
| e9 | e9_followup_en | V3 | 1 | 1.00 | 0.25 | — | 0.2981 |
| e9 | e9_reminder_day_en | V2 | 1 | 0.50 | 0.50 | — | 0.0980 |
| e9 | e9_reminder_day_en | V3 | 1 | 1.00 | 0.50 | — | 0.2585 |

## Experiment × condition (mean of scenario means)

| experiment | cond | scenarios | deterministic pass | judge | recall@prompt |
|---|---|---|---|---|---|
| e10 | V2 | 1 | 1.00 | 0.67 | — |
| e10 | V3 | 1 | 1.00 | 0.83 | — |
| e5 | V3 | 2 | 0.12 ± 1.51 | 0.07 ± 0.26 | — |
| e6 | V3 | 2 | 0.79 ± 0.53 | — | — |
| e7 | V3 | 1 | — | 0.00 | — |
| e8 | V2 | 2 | — | 0.88 ± 1.59 | — |
| e8 | V3 | 2 | — | 0.88 ± 1.59 | — |
| e9 | V2 | 2 | 0.25 ± 3.18 | 0.38 ± 1.59 | — |
| e9 | V3 | 2 | 1.00 ± 0.00 | 0.38 ± 1.59 | — |

## Per probe

| scenario | probe | cond | n | pass rate | judge | gold in prompt | reply words |
|---|---|---|---|---|---|---|---|
| e10_duplicates_en | cat | V2 | 1 | 1.00 | 0.50 | — | 74 |
| e10_duplicates_en | cat | V3 | 1 | 1.00 | 1.00 | — | 70 |
| e10_duplicates_en | race | V2 | 1 | 1.00 | 1.00 | — | 30 |
| e10_duplicates_en | race | V3 | 1 | 1.00 | 1.00 | — | 49 |
| e10_duplicates_en | sister | V2 | 1 | 1.00 | 0.50 | — | 37 |
| e10_duplicates_en | sister | V3 | 1 | 1.00 | 0.50 | — | 34 |
| e5_prose_en | garden_30d | V3 | 3 | 0.00 | 0.00 | — | 87 |
| e5_prose_en | programming_7d | V3 | 3 | 0.33 | 0.00 | — | 116 |
| e5_prose_en | programming_7d_false_belief | V3 | 3 | 0.00 | — | — | 189 |
| e5_prose_en | programming_7d_false_belief_says | V3 | 1 | — | 0.00 | — | 53 |
| e5_prose_en | programming_7d_no_lessons | V3 | 3 | 0.67 | — | — | 101 |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | V3 | 3 | 0.00 | — | — | 217 |
| e5_prose_en | programming_7d_no_selfmodel | V3 | 3 | 0.33 | — | — | 199 |
| e5_prose_en | programming_7d_says | V3 | 1 | — | 0.00 | — | 43 |
| e5_prose_en | sleep_1d | V3 | 3 | 0.33 | 0.33 | — | 106 |
| e5_short_en | garden_30d | V3 | 3 | 0.00 | 0.00 | — | 254 |
| e5_short_en | programming_7d | V3 | 3 | 0.00 | 0.00 | — | 254 |
| e5_short_en | programming_7d_no_lessons | V3 | 3 | 0.00 | — | — | 260 |
| e5_short_en | programming_7d_says | V3 | 1 | — | 0.50 | — | 120 |
| e5_short_en | sleep_1d | V3 | 3 | 0.00 | 0.00 | — | 225 |
| e6_prose_then_lists_en | after_phase1 | V3 | 3 | 0.67 | — | — | 245 |
| e6_prose_then_lists_en | phase2_2 | V3 | 3 | 0.67 | — | — | 250 |
| e6_prose_then_lists_en | phase2_4 | V3 | 3 | 1.00 | — | — | 238 |
| e6_prose_then_lists_en | phase2_6 | V3 | 3 | 1.00 | — | — | 254 |
| e6_short_then_long_en | after_phase1 | V3 | 3 | 0.00 | — | — | 199 |
| e6_short_then_long_en | phase2_2 | V3 | 3 | 1.00 | — | — | 184 |
| e6_short_then_long_en | phase2_4 | V3 | 3 | 1.00 | — | — | 211 |
| e6_short_then_long_en | phase2_6 | V3 | 3 | 1.00 | — | — | 253 |
| e7_reminder_en | first_message_5d | V3 | 1 | — | 0.00 | — | 177 |
| e7_reminder_en | first_message_5d_no_intentions | V3 | 1 | — | 0.00 | — | 152 |
| e8_decision_en | a_week | V2 | 1 | — | 1.00 | — | 38 |
| e8_decision_en | a_week | V3 | 1 | — | 1.00 | — | 93 |
| e8_decision_en | next_morning | V2 | 1 | — | 1.00 | — | 120 |
| e8_decision_en | next_morning | V3 | 1 | — | 1.00 | — | 191 |
| e8_decision_en | two_days | V2 | 1 | — | 1.00 | — | 149 |
| e8_decision_en | two_days | V3 | 1 | — | 1.00 | — | 125 |
| e8_puzzle_en | four_days | V2 | 1 | — | 0.50 | — | 148 |
| e8_puzzle_en | four_days | V3 | 1 | — | 0.50 | — | 164 |
| e8_puzzle_en | next_day | V2 | 1 | — | 1.00 | — | 172 |
| e8_puzzle_en | next_day | V3 | 1 | — | 1.00 | — | 90 |
| e9_followup_en | back_on_monday | V2 | 1 | — | 0.50 | — | 40 |
| e9_followup_en | back_on_monday | V3 | 1 | — | 0.50 | — | 54 |
| e9_followup_en | wrote_after_interview | V2 | 1 | 0.00 | 0.00 | — | 0 |
| e9_followup_en | wrote_after_interview | V3 | 1 | 1.00 | 0.00 | — | 45 |
| e9_reminder_day_en | back_on_sunday | V2 | 1 | — | 1.00 | — | 48 |
| e9_reminder_day_en | back_on_sunday | V3 | 1 | — | 1.00 | — | 25 |
| e9_reminder_day_en | nothing_before_thursday | V2 | 1 | 1.00 | — | — | 0 |
| e9_reminder_day_en | nothing_before_thursday | V3 | 1 | 1.00 | — | — | 0 |
| e9_reminder_day_en | wrote_on_thursday | V2 | 1 | 0.00 | 0.00 | — | 0 |
| e9_reminder_day_en | wrote_on_thursday | V3 | 1 | 1.00 | 0.00 | — | 46 |

## E4: behavioral measure vs B0

Effect = mean(condition) − mean(B0); d = Cohen's d. For V1 and V2 the effect is also split by whether any gold (originating) memory was in the prompt for the probe reply; for V2, also by whether any lesson was (change without retrieval: lesson shown, origin not).

n counts replies: probes with several questions (`asks:`) are pooled.

| scenario | probe | measure | cond | n | mean | B0 mean | effect | d | effect (origin in prompt / not) | effect (lesson shown / not) |
|---|---|---|---|---|---|---|---|---|---|---|
| e5_prose_en | garden_30d | bullets | V3 | 3 | 3.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_prose_en | programming_7d | bullets | V3 | 3 | 2.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_prose_en | programming_7d_false_belief | bullets | V3 | 3 | 7.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_prose_en | programming_7d_no_lessons | bullets | V3 | 3 | 1.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | bullets | V3 | 3 | 5.3 | — | — | — | — | — (n=0) / — (n=3) |
| e5_prose_en | programming_7d_no_selfmodel | bullets | V3 | 3 | 2.7 | — | — | — | — | — (n=0) / — (n=3) |
| e5_prose_en | sleep_1d | bullets | V3 | 3 | 2.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_short_en | garden_30d | words | V3 | 3 | 254.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_short_en | programming_7d | words | V3 | 3 | 254.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_short_en | programming_7d_no_lessons | words | V3 | 3 | 260.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_short_en | sleep_1d | words | V3 | 3 | 225.3 | — | — | — | — | — (n=0) / — (n=3) |
| e6_prose_then_lists_en | after_phase1 | bullets | V3 | 3 | 3.7 | — | — | — | — | — (n=0) / — (n=3) |
| e6_prose_then_lists_en | phase2_2 | bullets | V3 | 3 | 8.7 | — | — | — | — | — (n=0) / — (n=3) |
| e6_prose_then_lists_en | phase2_4 | bullets | V3 | 3 | 6.0 | — | — | — | — | — (n=3) / — (n=0) |
| e6_prose_then_lists_en | phase2_6 | bullets | V3 | 3 | 8.0 | — | — | — | — | — (n=3) / — (n=0) |
| e6_short_then_long_en | after_phase1 | words | V3 | 3 | 199.0 | — | — | — | — | — (n=3) / — (n=0) |
| e6_short_then_long_en | phase2_2 | words | V3 | 3 | 184.3 | — | — | — | — | — (n=3) / — (n=0) |
| e6_short_then_long_en | phase2_4 | words | V3 | 3 | 210.7 | — | — | — | — | — (n=3) / — (n=0) |
| e6_short_then_long_en | phase2_6 | words | V3 | 3 | 253.0 | — | — | — | — | — (n=3) / — (n=0) |

## Learning curves (key sessions, mean measure of the agent's replies)

| scenario | measure | cond | n | s1 | s2 | s3 | s4 | s5 | s6 | s7 | s8 | s9 | s10 | s11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e5_prose_en | bullets | V3 | 1 | 5.8 | 1.2 | 1.2 | 1.2 | 1.5 | 1.5 | — | — | — | — | — |
| e5_short_en | words | V3 | 1 | 150.5 | 130.2 | 121.5 | 166.0 | 112.2 | 129.5 | — | — | — | — | — |
| e6_prose_then_lists_en | bullets | V3 | 1 | 6.2 | 0.0 | 4.2 | 9.0 | 3.0 | 2.8 | 4.5 | 2.0 | 0.0 | 7.0 | 4.2 |
| e6_short_then_long_en | words | V3 | 1 | 141.0 | 81.0 | 112.0 | 32.2 | 72.0 | 124.2 | 122.2 | 98.8 | 130.8 | 106.8 | 139.8 |

## Self-report vs behavior

Claim = judge score of the self-report; behavior = pass rate of the paired probe's checks; divergence = mean |claim − behavior| over runs.

| scenario | self-report | paired probe | cond | n | claim | behavior | divergence |
|---|---|---|---|---|---|---|---|
| e5_prose_en | programming_7d_false_belief_says | programming_7d_false_belief | V3 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_says | programming_7d | V3 | 1 | 0.00 | 0.33 | 0.33 |
| e5_short_en | programming_7d_says | programming_7d | V3 | 1 | 0.50 | 0.00 | 0.50 |

## V2 state at the end of the run (mean over runs)

| scenario | cond | n | reactions | habits | active lessons | retired | adds | reinforces | weakens | portraits | beliefs grown without evidence | intentions done / dropped / open | chains complete |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e10_duplicates_en | V2 | 1 | 6.0 | 0.0 | 1.0 | 0.0 | 1.0 | 3.0 | 0.0 | 5.0 | 0.0 | 4.0 / 0.0 / 1.0 | 1.00 |
| e10_duplicates_en | V3 | 1 | 6.0 | 1.0 | 2.0 | 0.0 | 2.0 | 6.0 | 0.0 | 12.0 | 6.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e5_prose_en | V3 | 1 | 15.0 | 0.0 | 2.0 | 3.0 | 5.0 | 18.0 | 0.0 | 12.0 | 0.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e5_short_en | V3 | 1 | 8.0 | 0.0 | 4.0 | 3.0 | 7.0 | 17.0 | 1.0 | 11.0 | 0.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e6_prose_then_lists_en | V3 | 1 | 27.0 | 1.0 | 2.0 | 4.0 | 6.0 | 20.0 | 0.0 | 22.0 | 7.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e6_short_then_long_en | V3 | 1 | 28.0 | 1.0 | 5.0 | 4.0 | 9.0 | 18.0 | 1.0 | 21.0 | 5.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e7_reminder_en | V3 | 1 | 4.0 | 1.0 | 4.0 | 0.0 | 4.0 | 4.0 | 0.0 | 8.0 | 2.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e8_decision_en | V2 | 1 | 2.0 | 1.0 | 4.0 | 0.0 | 4.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 / 0.0 / 1.0 | 1.00 |
| e8_decision_en | V3 | 1 | 1.0 | 1.0 | 2.0 | 0.0 | 2.0 | 0.0 | 1.0 | 4.0 | 1.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e8_puzzle_en | V2 | 1 | 1.0 | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 / 0.0 / 1.0 | 1.00 |
| e8_puzzle_en | V3 | 1 | 1.0 | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 2.0 | 0.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e9_followup_en | V2 | 1 | 1.0 | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 1.0 | 0.0 | 1.0 / 1.0 / 1.0 | 1.00 |
| e9_followup_en | V3 | 1 | 2.0 | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 0.0 | 4.0 | 2.0 | 0.0 / 0.0 / 0.0 | 0.00 |
| e9_reminder_day_en | V2 | 1 | 2.0 | 0.0 | 2.0 | 0.0 | 2.0 | 0.0 | 0.0 | 1.0 | 0.0 | 1.0 / 0.0 / 1.0 | 1.00 |
| e9_reminder_day_en | V3 | 1 | 2.0 | 1.0 | 2.0 | 0.0 | 2.0 | 1.0 | 0.0 | 4.0 | 3.0 | 0.0 / 0.0 / 0.0 | 0.00 |

## V3: continuous cognition (mean over runs)

Cost per sim day = the run's total cost / its simulated span; wake and sleep calls run on the dialogue model, stream ticks on the cheap one.

| scenario | cond | n | sim days | stream thoughts | wakes (productive) | sleeps | merged | linked | retired in sleep | written first | own thoughts | stream $ | wake+sleep $ | $ / sim day |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e10_duplicates_en | V3 | 1 | 6.0 | 95 | 6.0 (6.0) | 6.0 | 0.0 | 21.0 | 0.0 | 1.0 | 11.0 | 0.018 | 0.192 | 0.079 |
| e5_prose_en | V3 | 1 | 40.0 | 686 | 14.0 (9.0) | 6.0 | 0.0 | 8.0 | 3.0 | 0.0 | 17.0 | 0.151 | 0.375 | 0.029 |
| e5_short_en | V3 | 1 | 40.0 | 686 | 18.0 (9.0) | 6.0 | 0.0 | 9.0 | 3.0 | 0.0 | 22.0 | 0.166 | 0.485 | 0.034 |
| e6_prose_then_lists_en | V3 | 1 | 22.0 | 385 | 11.0 (8.0) | 11.0 | 0.0 | 17.0 | 4.0 | 0.0 | 18.0 | 0.080 | 0.492 | 0.073 |
| e6_short_then_long_en | V3 | 1 | 22.0 | 385 | 10.0 (8.0) | 11.0 | 0.0 | 7.0 | 3.0 | 0.0 | 13.0 | 0.081 | 0.513 | 0.069 |
| e7_reminder_en | V3 | 1 | 5.0 | 82 | 4.0 (4.0) | 4.0 | 2.0 | 13.0 | 0.0 | 0.0 | 7.0 | 0.015 | 0.139 | 0.072 |
| e8_decision_en | V3 | 1 | 6.0 | 99 | 2.0 (2.0) | 2.0 | 0.0 | 5.0 | 0.0 | 1.0 | 3.0 | 0.027 | 0.147 | 0.054 |
| e8_puzzle_en | V3 | 1 | 4.0 | 68 | 1.0 (1.0) | 1.0 | 2.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.015 | 0.052 | 0.044 |
| e9_followup_en | V3 | 1 | 7.0 | 117 | 4.0 (3.0) | 2.0 | 0.0 | 4.0 | 0.0 | 1.0 | 5.0 | 0.038 | 0.147 | 0.043 |
| e9_reminder_day_en | V3 | 1 | 6.0 | 99 | 2.0 (2.0) | 2.0 | 0.0 | 5.0 | 0.0 | 1.0 | 3.0 | 0.034 | 0.116 | 0.043 |

## Initiative: messages written first before the probe

| scenario | probe | cond | n | wrote (share of runs) | messages | first at | judge |
|---|---|---|---|---|---|---|---|
| e9_followup_en | wrote_after_interview | V2 | 1 | 0.00 | 0.0 | — | 0.00 |
| e9_followup_en | wrote_after_interview | V3 | 1 | 1.00 | 1.0 | 2026-07-29T08:00 | 0.00 |
| e9_reminder_day_en | nothing_before_thursday | V2 | 1 | 0.00 | 0.0 | — | — |
| e9_reminder_day_en | nothing_before_thursday | V3 | 1 | 0.00 | 0.0 | — | — |
| e9_reminder_day_en | wrote_on_thursday | V2 | 1 | 0.00 | 0.0 | — | 0.00 |
| e9_reminder_day_en | wrote_on_thursday | V3 | 1 | 1.00 | 1.0 | 2026-07-20T22:04 | 0.00 |

## Cost

| cond | runs | mean cost/run $ | total spent $ | est. battery (all scenarios × N=5) $ |
|---|---|---|---|---|
| V2 | 5 | 0.1283 | 0.6417 | 3.21 |
| V3 | 10 | 0.7558 | 7.5577 | 37.79 |

Battery estimate covers only scenarios run so far; missing pairs: 5.

## Judge spot-check

Wrote 5 of 49 judged items to results/raw/v3-pass1/spotcheck.csv (judge scores and conditions hidden). Fill in human_score (0, 0.5, 1) and re-run the report to get agreement.
