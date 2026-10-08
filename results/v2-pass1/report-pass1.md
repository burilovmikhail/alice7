# Report: results/raw/v2-pass1

54 runs, conditions: B0, B1, B2, B3, V1, V2

Left out 3 degraded run(s) with failed agent model calls (rerun with `run --skip-existing`): 2026-10-08-e5_short_en-V1-1 (main/episode: 1, probe-base/episode: 2, probe/embed: 1); 2026-10-08-e6_short_then_long_en-V2-1 (main/embed: 3); 2026-10-08-e7_reminder_en-V2-1 (main/embed: 1)

## Scenario × condition (mean ± 95% CI over runs)

| experiment | scenario | cond | n | deterministic pass | judge | recall@prompt | cost/run $ |
|---|---|---|---|---|---|---|---|
| e5 | e5_emoji_en | B0 | 1 | 0.00 | — | — | 0.1742 |
| e5 | e5_emoji_en | B1 | 1 | 0.08 | — | — | 0.4553 |
| e5 | e5_emoji_en | B2 | 1 | 0.17 | — | — | 0.2237 |
| e5 | e5_emoji_en | B3 | 1 | 0.00 | — | — | 0.2624 |
| e5 | e5_emoji_en | V1 | 1 | 0.17 | — | — | 0.2123 |
| e5 | e5_emoji_en | V2 | 1 | 0.75 | — | — | 0.6104 |
| e5 | e5_long_prose_en | B0 | 1 | 0.33 | 0.00 | — | 0.4523 |
| e5 | e5_long_prose_en | B1 | 1 | 0.11 | 0.00 | — | 2.8835 |
| e5 | e5_long_prose_en | B2 | 1 | 0.22 | 0.17 | — | 1.0497 |
| e5 | e5_long_prose_en | B3 | 1 | 0.33 | 0.50 | — | 3.7905 |
| e5 | e5_long_prose_en | V1 | 1 | 0.33 | 0.00 | — | 0.7084 |
| e5 | e5_long_prose_en | V2 | 1 | 0.11 | 0.00 | — | 1.8280 |
| e5 | e5_no_questions_en | B0 | 1 | 0.67 | — | — | 0.1887 |
| e5 | e5_no_questions_en | B1 | 1 | 0.25 | — | — | 0.5575 |
| e5 | e5_no_questions_en | B2 | 1 | 0.33 | — | — | 0.2605 |
| e5 | e5_no_questions_en | B3 | 1 | 0.58 | — | — | 0.4259 |
| e5 | e5_no_questions_en | V1 | 1 | 0.33 | — | — | 0.2528 |
| e5 | e5_no_questions_en | V2 | 1 | 0.67 | — | — | 0.3944 |
| e5 | e5_prose_en | B0 | 1 | 0.14 | 0.23 | — | 0.3007 |
| e5 | e5_prose_en | B1 | 1 | 0.00 | 0.00 | — | 0.9542 |
| e5 | e5_prose_en | B2 | 1 | 0.10 | 0.09 | — | 0.3991 |
| e5 | e5_prose_en | B3 | 1 | 0.00 | 0.00 | — | 0.5280 |
| e5 | e5_prose_en | V1 | 1 | 0.10 | 0.00 | — | 0.3497 |
| e5 | e5_prose_en | V2 | 1 | 0.05 | 0.05 | — | 0.5589 |
| e5 | e5_short_en | B0 | 1 | 0.00 | 0.00 | — | 0.2041 |
| e5 | e5_short_en | B1 | 1 | 0.00 | 0.00 | — | 0.8097 |
| e5 | e5_short_en | B2 | 1 | 0.00 | 0.00 | — | 0.3300 |
| e5 | e5_short_en | B3 | 1 | 1.00 | 1.00 | — | 0.3891 |
| e5 | e5_short_en | V1 | 1 | 0.00 | 0.00 | — | 0.3357 |
| e5 | e5_short_en | V2 | 1 | 0.83 | 1.00 | — | 0.5663 |
| e6 | e6_prose_then_lists_en | B0 | 1 | 0.92 | — | — | 0.2934 |
| e6 | e6_prose_then_lists_en | B1 | 1 | 0.75 | — | — | 1.2782 |
| e6 | e6_prose_then_lists_en | B2 | 1 | 0.83 | — | — | 0.4343 |
| e6 | e6_prose_then_lists_en | B3 | 1 | 0.67 | — | — | 0.8168 |
| e6 | e6_prose_then_lists_en | V1 | 1 | 0.67 | — | — | 0.4569 |
| e6 | e6_prose_then_lists_en | V2 | 1 | 0.75 | — | — | 1.0415 |
| e6 | e6_short_then_long_en | B0 | 1 | 0.75 | — | — | 0.2951 |
| e6 | e6_short_then_long_en | B1 | 1 | 0.75 | — | — | 1.5581 |
| e6 | e6_short_then_long_en | B2 | 1 | 0.75 | — | — | 0.4131 |
| e6 | e6_short_then_long_en | B3 | 1 | 0.75 | — | — | 1.0163 |
| e6 | e6_short_then_long_en | V1 | 1 | 0.75 | — | — | 0.4605 |
| e6 | e6_short_then_long_en | V2 | 1 | 0.58 | — | — | 0.8266 |
| e7 | e7_reminder_en | B0 | 1 | — | 0.00 | — | 0.0526 |
| e7 | e7_reminder_en | B1 | 1 | — | 1.00 | — | 0.0770 |
| e7 | e7_reminder_en | B2 | 1 | — | 0.00 | — | 0.0743 |
| e7 | e7_reminder_en | B3 | 1 | — | 0.50 | — | 0.1427 |
| e7 | e7_reminder_en | V1 | 1 | — | 0.50 | — | 0.0758 |
| e7 | e7_reminder_en | V2 | 1 | — | 0.00 | — | 0.2150 |
| e7 | e7_venting_en | B0 | 1 | — | 1.00 | — | 0.1153 |
| e7 | e7_venting_en | B1 | 1 | — | 1.00 | — | 0.2462 |
| e7 | e7_venting_en | B2 | 1 | — | 1.00 | — | 0.1385 |
| e7 | e7_venting_en | B3 | 1 | — | 1.00 | — | 0.3883 |
| e7 | e7_venting_en | V1 | 1 | — | 1.00 | — | 0.1556 |
| e7 | e7_venting_en | V2 | 1 | — | 1.00 | — | 0.4469 |

## Experiment × condition (mean of scenario means)

| experiment | cond | scenarios | deterministic pass | judge | recall@prompt |
|---|---|---|---|---|---|
| e5 | B0 | 5 | 0.23 ± 0.35 | 0.08 ± 0.33 | — |
| e5 | B1 | 5 | 0.09 ± 0.13 | 0.00 ± 0.00 | — |
| e5 | B2 | 5 | 0.16 ± 0.16 | 0.09 ± 0.21 | — |
| e5 | B3 | 5 | 0.38 ± 0.53 | 0.50 ± 1.24 | — |
| e5 | V1 | 5 | 0.19 ± 0.18 | 0.00 ± 0.00 | — |
| e5 | V2 | 5 | 0.48 ± 0.46 | 0.35 ± 1.40 | — |
| e6 | B0 | 2 | 0.83 ± 1.06 | — | — |
| e6 | B1 | 2 | 0.75 ± 0.00 | — | — |
| e6 | B2 | 2 | 0.79 ± 0.53 | — | — |
| e6 | B3 | 2 | 0.71 ± 0.53 | — | — |
| e6 | V1 | 2 | 0.71 ± 0.53 | — | — |
| e6 | V2 | 2 | 0.67 ± 1.06 | — | — |
| e7 | B0 | 2 | — | 0.50 ± 6.35 | — |
| e7 | B1 | 2 | — | 1.00 ± 0.00 | — |
| e7 | B2 | 2 | — | 0.50 ± 6.35 | — |
| e7 | B3 | 2 | — | 0.75 ± 3.18 | — |
| e7 | V1 | 2 | — | 0.75 ± 3.18 | — |
| e7 | V2 | 2 | — | 0.50 ± 6.35 | — |

## Per probe

| scenario | probe | cond | n | pass rate | judge | gold in prompt | reply words |
|---|---|---|---|---|---|---|---|
| e5_emoji_en | garden_30d | B0 | 3 | 0.00 | — | — | 266 |
| e5_emoji_en | garden_30d | B1 | 3 | 0.33 | — | — | 290 |
| e5_emoji_en | garden_30d | B2 | 3 | 0.67 | — | — | 277 |
| e5_emoji_en | garden_30d | B3 | 3 | 0.00 | — | — | 106 |
| e5_emoji_en | garden_30d | V1 | 3 | 0.33 | — | — | 239 |
| e5_emoji_en | garden_30d | V2 | 3 | 1.00 | — | — | 218 |
| e5_emoji_en | programming_7d | B0 | 3 | 0.00 | — | — | 288 |
| e5_emoji_en | programming_7d | B1 | 3 | 0.00 | — | — | 268 |
| e5_emoji_en | programming_7d | B2 | 3 | 0.00 | — | — | 279 |
| e5_emoji_en | programming_7d | B3 | 3 | 0.00 | — | — | 84 |
| e5_emoji_en | programming_7d | V1 | 3 | 0.00 | — | — | 192 |
| e5_emoji_en | programming_7d | V2 | 3 | 1.00 | — | — | 202 |
| e5_emoji_en | programming_7d_no_lessons | B0 | 3 | 0.00 | — | — | 257 |
| e5_emoji_en | programming_7d_no_lessons | B1 | 3 | 0.00 | — | — | 273 |
| e5_emoji_en | programming_7d_no_lessons | B2 | 3 | 0.00 | — | — | 255 |
| e5_emoji_en | programming_7d_no_lessons | B3 | 3 | 0.00 | — | — | 83 |
| e5_emoji_en | programming_7d_no_lessons | V1 | 3 | 0.00 | — | — | 206 |
| e5_emoji_en | programming_7d_no_lessons | V2 | 3 | 0.00 | — | — | 235 |
| e5_emoji_en | sleep_1d | B0 | 3 | 0.00 | — | — | 264 |
| e5_emoji_en | sleep_1d | B1 | 3 | 0.00 | — | — | 287 |
| e5_emoji_en | sleep_1d | B2 | 3 | 0.00 | — | — | 295 |
| e5_emoji_en | sleep_1d | B3 | 3 | 0.00 | — | — | 91 |
| e5_emoji_en | sleep_1d | V1 | 3 | 0.33 | — | — | 197 |
| e5_emoji_en | sleep_1d | V2 | 3 | 1.00 | — | — | 188 |
| e5_long_prose_en | garden_60d | B0 | 3 | 0.00 | 0.00 | — | 267 |
| e5_long_prose_en | garden_60d | B1 | 3 | 0.00 | 0.00 | — | 456 |
| e5_long_prose_en | garden_60d | B2 | 3 | 0.33 | 0.33 | — | 307 |
| e5_long_prose_en | garden_60d | B3 | 3 | 0.33 | 0.33 | — | 179 |
| e5_long_prose_en | garden_60d | V1 | 3 | 0.33 | 0.00 | — | 248 |
| e5_long_prose_en | garden_60d | V2 | 3 | 0.33 | 0.00 | — | 242 |
| e5_long_prose_en | garden_60d_no_lessons | B0 | 3 | 0.33 | — | — | 288 |
| e5_long_prose_en | garden_60d_no_lessons | B1 | 3 | 0.00 | — | — | 442 |
| e5_long_prose_en | garden_60d_no_lessons | B2 | 3 | 0.00 | — | — | 315 |
| e5_long_prose_en | garden_60d_no_lessons | B3 | 3 | 0.00 | — | — | 240 |
| e5_long_prose_en | garden_60d_no_lessons | V1 | 3 | 0.33 | — | — | 259 |
| e5_long_prose_en | garden_60d_no_lessons | V2 | 3 | 0.00 | — | — | 231 |
| e5_long_prose_en | sleep_30d | B0 | 3 | 0.67 | 0.00 | — | 275 |
| e5_long_prose_en | sleep_30d | B1 | 3 | 0.33 | 0.00 | — | 378 |
| e5_long_prose_en | sleep_30d | B2 | 3 | 0.33 | 0.00 | — | 273 |
| e5_long_prose_en | sleep_30d | B3 | 3 | 0.67 | 0.67 | — | 64 |
| e5_long_prose_en | sleep_30d | V1 | 3 | 0.33 | 0.00 | — | 203 |
| e5_long_prose_en | sleep_30d | V2 | 3 | 0.00 | 0.00 | — | 127 |
| e5_no_questions_en | garden_30d | B0 | 3 | 1.00 | — | — | 272 |
| e5_no_questions_en | garden_30d | B1 | 3 | 0.00 | — | — | 415 |
| e5_no_questions_en | garden_30d | B2 | 3 | 0.33 | — | — | 289 |
| e5_no_questions_en | garden_30d | B3 | 3 | 0.67 | — | — | 141 |
| e5_no_questions_en | garden_30d | V1 | 3 | 0.67 | — | — | 194 |
| e5_no_questions_en | garden_30d | V2 | 3 | 1.00 | — | — | 34 |
| e5_no_questions_en | programming_7d | B0 | 3 | 0.67 | — | — | 279 |
| e5_no_questions_en | programming_7d | B1 | 3 | 0.33 | — | — | 430 |
| e5_no_questions_en | programming_7d | B2 | 3 | 0.33 | — | — | 301 |
| e5_no_questions_en | programming_7d | B3 | 3 | 0.00 | — | — | 133 |
| e5_no_questions_en | programming_7d | V1 | 3 | 0.00 | — | — | 246 |
| e5_no_questions_en | programming_7d | V2 | 3 | 0.67 | — | — | 76 |
| e5_no_questions_en | programming_7d_no_lessons | B0 | 3 | 0.67 | — | — | 264 |
| e5_no_questions_en | programming_7d_no_lessons | B1 | 3 | 0.33 | — | — | 372 |
| e5_no_questions_en | programming_7d_no_lessons | B2 | 3 | 0.33 | — | — | 305 |
| e5_no_questions_en | programming_7d_no_lessons | B3 | 3 | 0.67 | — | — | 134 |
| e5_no_questions_en | programming_7d_no_lessons | V1 | 3 | 0.33 | — | — | 228 |
| e5_no_questions_en | programming_7d_no_lessons | V2 | 3 | 0.33 | — | — | 93 |
| e5_no_questions_en | sleep_1d | B0 | 3 | 0.33 | — | — | 252 |
| e5_no_questions_en | sleep_1d | B1 | 3 | 0.33 | — | — | 427 |
| e5_no_questions_en | sleep_1d | B2 | 3 | 0.33 | — | — | 288 |
| e5_no_questions_en | sleep_1d | B3 | 3 | 1.00 | — | — | 117 |
| e5_no_questions_en | sleep_1d | V1 | 3 | 0.33 | — | — | 249 |
| e5_no_questions_en | sleep_1d | V2 | 3 | 0.67 | — | — | 48 |
| e5_prose_en | garden_30d | B0 | 3 | 0.33 | 0.00 | — | 276 |
| e5_prose_en | garden_30d | B1 | 3 | 0.00 | 0.00 | — | 420 |
| e5_prose_en | garden_30d | B2 | 3 | 0.00 | 0.00 | — | 302 |
| e5_prose_en | garden_30d | B3 | 3 | 0.00 | 0.00 | — | 132 |
| e5_prose_en | garden_30d | V1 | 3 | 0.00 | 0.00 | — | 180 |
| e5_prose_en | garden_30d | V2 | 3 | 0.00 | 0.00 | — | 49 |
| e5_prose_en | programming_7d | B0 | 3 | 0.00 | 0.00 | — | 273 |
| e5_prose_en | programming_7d | B1 | 3 | 0.00 | 0.00 | — | 387 |
| e5_prose_en | programming_7d | B2 | 3 | 0.00 | 0.00 | — | 284 |
| e5_prose_en | programming_7d | B3 | 3 | 0.00 | 0.00 | — | 121 |
| e5_prose_en | programming_7d | V1 | 3 | 0.33 | 0.00 | — | 175 |
| e5_prose_en | programming_7d | V2 | 3 | 0.00 | 0.00 | — | 48 |
| e5_prose_en | programming_7d_false_belief | B0 | 3 | 0.00 | — | — | 253 |
| e5_prose_en | programming_7d_false_belief | B1 | 3 | 0.00 | — | — | 381 |
| e5_prose_en | programming_7d_false_belief | B2 | 3 | 0.00 | — | — | 287 |
| e5_prose_en | programming_7d_false_belief | B3 | 3 | 0.00 | — | — | 121 |
| e5_prose_en | programming_7d_false_belief | V1 | 3 | 0.00 | — | — | 177 |
| e5_prose_en | programming_7d_false_belief | V2 | 3 | 0.00 | — | — | 59 |
| e5_prose_en | programming_7d_false_belief_says | B0 | 1 | — | 1.00 | — | 81 |
| e5_prose_en | programming_7d_false_belief_says | B1 | 1 | — | 0.00 | — | 106 |
| e5_prose_en | programming_7d_false_belief_says | B2 | 1 | — | 0.00 | — | 131 |
| e5_prose_en | programming_7d_false_belief_says | B3 | 1 | — | 0.00 | — | 87 |
| e5_prose_en | programming_7d_false_belief_says | V1 | 1 | — | 0.00 | — | 62 |
| e5_prose_en | programming_7d_false_belief_says | V2 | 1 | — | 0.00 | — | 43 |
| e5_prose_en | programming_7d_no_lessons | B0 | 3 | 0.00 | — | — | 265 |
| e5_prose_en | programming_7d_no_lessons | B1 | 3 | 0.00 | — | — | 412 |
| e5_prose_en | programming_7d_no_lessons | B2 | 3 | 0.00 | — | — | 295 |
| e5_prose_en | programming_7d_no_lessons | B3 | 3 | 0.00 | — | — | 113 |
| e5_prose_en | programming_7d_no_lessons | V1 | 3 | 0.33 | — | — | 188 |
| e5_prose_en | programming_7d_no_lessons | V2 | 3 | 0.00 | — | — | 67 |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | B0 | 3 | 0.00 | — | — | 243 |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | B1 | 3 | 0.00 | — | — | 381 |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | B2 | 3 | 0.00 | — | — | 314 |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | B3 | 3 | 0.00 | — | — | 115 |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | V1 | 3 | 0.00 | — | — | 189 |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | V2 | 3 | 0.33 | — | — | 239 |
| e5_prose_en | programming_7d_no_selfmodel | B0 | 3 | 0.00 | — | — | 245 |
| e5_prose_en | programming_7d_no_selfmodel | B1 | 3 | 0.00 | — | — | 396 |
| e5_prose_en | programming_7d_no_selfmodel | B2 | 3 | 0.00 | — | — | 319 |
| e5_prose_en | programming_7d_no_selfmodel | B3 | 3 | 0.00 | — | — | 116 |
| e5_prose_en | programming_7d_no_selfmodel | V1 | 3 | 0.00 | — | — | 197 |
| e5_prose_en | programming_7d_no_selfmodel | V2 | 3 | 0.00 | — | — | 62 |
| e5_prose_en | programming_7d_says | B0 | 1 | — | 1.00 | — | 109 |
| e5_prose_en | programming_7d_says | B1 | 1 | — | 0.00 | — | 77 |
| e5_prose_en | programming_7d_says | B2 | 1 | — | 1.00 | — | 105 |
| e5_prose_en | programming_7d_says | B3 | 1 | — | 0.00 | — | 55 |
| e5_prose_en | programming_7d_says | V1 | 1 | — | 0.00 | — | 73 |
| e5_prose_en | programming_7d_says | V2 | 1 | — | 0.50 | — | 15 |
| e5_prose_en | sleep_1d | B0 | 3 | 0.67 | 0.17 | — | 256 |
| e5_prose_en | sleep_1d | B1 | 3 | 0.00 | 0.00 | — | 405 |
| e5_prose_en | sleep_1d | B2 | 3 | 0.67 | 0.00 | — | 315 |
| e5_prose_en | sleep_1d | B3 | 3 | 0.00 | 0.00 | — | 113 |
| e5_prose_en | sleep_1d | V1 | 3 | 0.00 | 0.00 | — | 198 |
| e5_prose_en | sleep_1d | V2 | 3 | 0.00 | 0.00 | — | 63 |
| e5_short_en | garden_30d | B0 | 3 | 0.00 | 0.00 | — | 264 |
| e5_short_en | garden_30d | B1 | 3 | 0.00 | 0.00 | — | 478 |
| e5_short_en | garden_30d | B2 | 3 | 0.00 | 0.00 | — | 310 |
| e5_short_en | garden_30d | B3 | 3 | 1.00 | 1.00 | — | 117 |
| e5_short_en | garden_30d | V1 | 3 | 0.00 | 0.00 | — | 257 |
| e5_short_en | garden_30d | V2 | 3 | 0.33 | 1.00 | — | 150 |
| e5_short_en | programming_7d | B0 | 3 | 0.00 | 0.00 | — | 230 |
| e5_short_en | programming_7d | B1 | 3 | 0.00 | 0.00 | — | 467 |
| e5_short_en | programming_7d | B2 | 3 | 0.00 | 0.00 | — | 340 |
| e5_short_en | programming_7d | B3 | 3 | 1.00 | 1.00 | — | 94 |
| e5_short_en | programming_7d | V1 | 3 | 0.00 | 0.00 | — | 254 |
| e5_short_en | programming_7d | V2 | 3 | 1.00 | 1.00 | — | 140 |
| e5_short_en | programming_7d_no_lessons | B0 | 3 | — | — | — | — |
| e5_short_en | programming_7d_no_lessons | B1 | 3 | 0.00 | — | — | 498 |
| e5_short_en | programming_7d_no_lessons | B2 | 3 | 0.00 | — | — | 306 |
| e5_short_en | programming_7d_no_lessons | B3 | 3 | 1.00 | — | — | 103 |
| e5_short_en | programming_7d_no_lessons | V1 | 3 | 0.00 | — | — | 239 |
| e5_short_en | programming_7d_no_lessons | V2 | 3 | 1.00 | — | — | 104 |
| e5_short_en | programming_7d_says | B0 | 1 | — | — | — | — |
| e5_short_en | programming_7d_says | B1 | 1 | — | 0.00 | — | 72 |
| e5_short_en | programming_7d_says | B2 | 1 | — | 0.00 | — | 83 |
| e5_short_en | programming_7d_says | B3 | 1 | — | 1.00 | — | 58 |
| e5_short_en | programming_7d_says | V1 | 1 | — | 0.00 | — | 84 |
| e5_short_en | programming_7d_says | V2 | 1 | — | 1.00 | — | 89 |
| e5_short_en | sleep_1d | B0 | 3 | 0.00 | 0.00 | — | 261 |
| e5_short_en | sleep_1d | B1 | 3 | 0.00 | 0.00 | — | 458 |
| e5_short_en | sleep_1d | B2 | 3 | 0.00 | 0.00 | — | 333 |
| e5_short_en | sleep_1d | B3 | 3 | 1.00 | 1.00 | — | 123 |
| e5_short_en | sleep_1d | V1 | 3 | 0.00 | 0.00 | — | 241 |
| e5_short_en | sleep_1d | V2 | 3 | 1.00 | 1.00 | — | 105 |
| e6_prose_then_lists_en | after_phase1 | B0 | 3 | 0.67 | — | — | 272 |
| e6_prose_then_lists_en | after_phase1 | B1 | 3 | 0.00 | — | — | 324 |
| e6_prose_then_lists_en | after_phase1 | B2 | 3 | 0.67 | — | — | 281 |
| e6_prose_then_lists_en | after_phase1 | B3 | 3 | 0.00 | — | — | 177 |
| e6_prose_then_lists_en | after_phase1 | V1 | 3 | 0.33 | — | — | 224 |
| e6_prose_then_lists_en | after_phase1 | V2 | 3 | 0.00 | — | — | 103 |
| e6_prose_then_lists_en | phase2_2 | B0 | 3 | 1.00 | — | — | 258 |
| e6_prose_then_lists_en | phase2_2 | B1 | 3 | 1.00 | — | — | 375 |
| e6_prose_then_lists_en | phase2_2 | B2 | 3 | 1.00 | — | — | 317 |
| e6_prose_then_lists_en | phase2_2 | B3 | 3 | 1.00 | — | — | 192 |
| e6_prose_then_lists_en | phase2_2 | V1 | 3 | 1.00 | — | — | 251 |
| e6_prose_then_lists_en | phase2_2 | V2 | 3 | 1.00 | — | — | 229 |
| e6_prose_then_lists_en | phase2_4 | B0 | 3 | 1.00 | — | — | 287 |
| e6_prose_then_lists_en | phase2_4 | B1 | 3 | 1.00 | — | — | 401 |
| e6_prose_then_lists_en | phase2_4 | B2 | 3 | 0.67 | — | — | 294 |
| e6_prose_then_lists_en | phase2_4 | B3 | 3 | 1.00 | — | — | 209 |
| e6_prose_then_lists_en | phase2_4 | V1 | 3 | 0.67 | — | — | 231 |
| e6_prose_then_lists_en | phase2_4 | V2 | 3 | 1.00 | — | — | 250 |
| e6_prose_then_lists_en | phase2_6 | B0 | 3 | 1.00 | — | — | 235 |
| e6_prose_then_lists_en | phase2_6 | B1 | 3 | 1.00 | — | — | 454 |
| e6_prose_then_lists_en | phase2_6 | B2 | 3 | 1.00 | — | — | 339 |
| e6_prose_then_lists_en | phase2_6 | B3 | 3 | 0.67 | — | — | 210 |
| e6_prose_then_lists_en | phase2_6 | V1 | 3 | 0.67 | — | — | 282 |
| e6_prose_then_lists_en | phase2_6 | V2 | 3 | 1.00 | — | — | 293 |
| e6_short_then_long_en | after_phase1 | B0 | 3 | 0.00 | — | — | 288 |
| e6_short_then_long_en | after_phase1 | B1 | 3 | 0.00 | — | — | 423 |
| e6_short_then_long_en | after_phase1 | B2 | 3 | 0.00 | — | — | 318 |
| e6_short_then_long_en | after_phase1 | B3 | 3 | 0.00 | — | — | 278 |
| e6_short_then_long_en | after_phase1 | V1 | 3 | 0.00 | — | — | 224 |
| e6_short_then_long_en | after_phase1 | V2 | 3 | 1.00 | — | — | 94 |
| e6_short_then_long_en | phase2_2 | B0 | 3 | 1.00 | — | — | 264 |
| e6_short_then_long_en | phase2_2 | B1 | 3 | 1.00 | — | — | 464 |
| e6_short_then_long_en | phase2_2 | B2 | 3 | 1.00 | — | — | 263 |
| e6_short_then_long_en | phase2_2 | B3 | 3 | 1.00 | — | — | 265 |
| e6_short_then_long_en | phase2_2 | V1 | 3 | 1.00 | — | — | 247 |
| e6_short_then_long_en | phase2_2 | V2 | 3 | 0.00 | — | — | 9 |
| e6_short_then_long_en | phase2_4 | B0 | 3 | 1.00 | — | — | 268 |
| e6_short_then_long_en | phase2_4 | B1 | 3 | 1.00 | — | — | 529 |
| e6_short_then_long_en | phase2_4 | B2 | 3 | 1.00 | — | — | 310 |
| e6_short_then_long_en | phase2_4 | B3 | 3 | 1.00 | — | — | 314 |
| e6_short_then_long_en | phase2_4 | V1 | 3 | 1.00 | — | — | 265 |
| e6_short_then_long_en | phase2_4 | V2 | 3 | 1.00 | — | — | 176 |
| e6_short_then_long_en | phase2_6 | B0 | 3 | 1.00 | — | — | 259 |
| e6_short_then_long_en | phase2_6 | B1 | 3 | 1.00 | — | — | 550 |
| e6_short_then_long_en | phase2_6 | B2 | 3 | 1.00 | — | — | 262 |
| e6_short_then_long_en | phase2_6 | B3 | 3 | 1.00 | — | — | 319 |
| e6_short_then_long_en | phase2_6 | V1 | 3 | 1.00 | — | — | 275 |
| e6_short_then_long_en | phase2_6 | V2 | 3 | 0.33 | — | — | 161 |
| e7_reminder_en | first_message_5d | B0 | 1 | — | 0.00 | — | 126 |
| e7_reminder_en | first_message_5d | B1 | 1 | — | 1.00 | — | 144 |
| e7_reminder_en | first_message_5d | B2 | 1 | — | 0.00 | — | 151 |
| e7_reminder_en | first_message_5d | B3 | 1 | — | 1.00 | — | 136 |
| e7_reminder_en | first_message_5d | V1 | 1 | — | 1.00 | — | 137 |
| e7_reminder_en | first_message_5d | V2 | 1 | — | 0.00 | — | 132 |
| e7_reminder_en | first_message_5d_no_intentions | B0 | 1 | — | 0.00 | — | 80 |
| e7_reminder_en | first_message_5d_no_intentions | B1 | 1 | — | 1.00 | — | 163 |
| e7_reminder_en | first_message_5d_no_intentions | B2 | 1 | — | 0.00 | — | 170 |
| e7_reminder_en | first_message_5d_no_intentions | B3 | 1 | — | 0.00 | — | 163 |
| e7_reminder_en | first_message_5d_no_intentions | V1 | 1 | — | 0.00 | — | 170 |
| e7_reminder_en | first_message_5d_no_intentions | V2 | 1 | — | 0.00 | — | 156 |
| e7_venting_en | grandmother_25d | B0 | 1 | — | 1.00 | — | 92 |
| e7_venting_en | grandmother_25d | B1 | 1 | — | 1.00 | — | 92 |
| e7_venting_en | grandmother_25d | B2 | 1 | — | 1.00 | — | 61 |
| e7_venting_en | grandmother_25d | B3 | 1 | — | 1.00 | — | 45 |
| e7_venting_en | grandmother_25d | V1 | 1 | — | 1.00 | — | 76 |
| e7_venting_en | grandmother_25d | V2 | 1 | — | 1.00 | — | 117 |
| e7_venting_en | grandmother_25d_no_lessons | B0 | 1 | — | 1.00 | — | 79 |
| e7_venting_en | grandmother_25d_no_lessons | B1 | 1 | — | 1.00 | — | 81 |
| e7_venting_en | grandmother_25d_no_lessons | B2 | 1 | — | 1.00 | — | 74 |
| e7_venting_en | grandmother_25d_no_lessons | B3 | 1 | — | 1.00 | — | 49 |
| e7_venting_en | grandmother_25d_no_lessons | V1 | 1 | — | 1.00 | — | 75 |
| e7_venting_en | grandmother_25d_no_lessons | V2 | 1 | — | 1.00 | — | 103 |

## E4: behavioral measure vs B0

Effect = mean(condition) − mean(B0); d = Cohen's d. For V1 and V2 the effect is also split by whether any gold (originating) memory was in the prompt for the probe reply; for V2, also by whether any lesson was (change without retrieval: lesson shown, origin not).

n counts replies: probes with several questions (`asks:`) are pooled.

| scenario | probe | measure | cond | n | mean | B0 mean | effect | d | effect (origin in prompt / not) | effect (lesson shown / not) |
|---|---|---|---|---|---|---|---|---|---|---|
| e5_emoji_en | garden_30d | emoji | B1 | 3 | 0.3 | 0.0 | 0.3 | 0.82 | — | — |
| e5_emoji_en | garden_30d | emoji | B2 | 3 | 0.7 | 0.0 | 0.7 | 1.63 | — | — |
| e5_emoji_en | garden_30d | emoji | B3 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | garden_30d | emoji | V1 | 3 | 0.3 | 0.0 | 0.3 | 0.82 | — | — |
| e5_emoji_en | garden_30d | emoji | V2 | 3 | 1.7 | 0.0 | 1.7 | 2.04 | — | 1.7 (n=3) / — (n=0) |
| e5_emoji_en | programming_7d | emoji | B1 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d | emoji | B2 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d | emoji | B3 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d | emoji | V1 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d | emoji | V2 | 3 | 1.3 | 0.0 | 1.3 | 3.27 | — | 1.3 (n=3) / — (n=0) |
| e5_emoji_en | programming_7d_no_lessons | emoji | B1 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d_no_lessons | emoji | B2 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d_no_lessons | emoji | B3 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d_no_lessons | emoji | V1 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | programming_7d_no_lessons | emoji | V2 | 3 | 0.0 | 0.0 | 0.0 | — | — | — (n=0) / 0.0 (n=3) |
| e5_emoji_en | sleep_1d | emoji | B1 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | sleep_1d | emoji | B2 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | sleep_1d | emoji | B3 | 3 | 0.0 | 0.0 | 0.0 | — | — | — |
| e5_emoji_en | sleep_1d | emoji | V1 | 3 | 0.3 | 0.0 | 0.3 | 0.82 | — | — |
| e5_emoji_en | sleep_1d | emoji | V2 | 3 | 1.7 | 0.0 | 1.7 | 2.04 | — | 1.7 (n=3) / — (n=0) |
| e5_long_prose_en | garden_60d | bullets | B1 | 3 | 15.3 | 10.3 | 5.0 | 0.77 | — | — |
| e5_long_prose_en | garden_60d | bullets | B2 | 3 | 8.3 | 10.3 | -2.0 | -0.29 | — | — |
| e5_long_prose_en | garden_60d | bullets | B3 | 3 | 5.7 | 10.3 | -4.7 | -0.73 | — | — |
| e5_long_prose_en | garden_60d | bullets | V1 | 3 | 7.0 | 10.3 | -3.3 | -0.52 | — | — |
| e5_long_prose_en | garden_60d | bullets | V2 | 3 | 3.7 | 10.3 | -6.7 | -1.21 | — | -6.7 (n=3) / — (n=0) |
| e5_long_prose_en | garden_60d_no_lessons | bullets | B1 | 3 | 11.7 | 11.3 | 0.3 | 0.04 | — | — |
| e5_long_prose_en | garden_60d_no_lessons | bullets | B2 | 3 | 9.7 | 11.3 | -1.7 | -0.21 | — | — |
| e5_long_prose_en | garden_60d_no_lessons | bullets | B3 | 3 | 6.0 | 11.3 | -5.3 | -0.74 | — | — |
| e5_long_prose_en | garden_60d_no_lessons | bullets | V1 | 3 | 8.0 | 11.3 | -3.3 | -0.38 | — | — |
| e5_long_prose_en | garden_60d_no_lessons | bullets | V2 | 3 | 6.3 | 11.3 | -5.0 | -0.68 | — | — (n=0) / -5.0 (n=3) |
| e5_long_prose_en | sleep_30d | bullets | B1 | 3 | 8.0 | 4.3 | 3.7 | 0.49 | — | — |
| e5_long_prose_en | sleep_30d | bullets | B2 | 3 | 6.7 | 4.3 | 2.3 | 0.32 | — | — |
| e5_long_prose_en | sleep_30d | bullets | B3 | 3 | 1.7 | 4.3 | -2.7 | -0.47 | — | — |
| e5_long_prose_en | sleep_30d | bullets | V1 | 3 | 4.0 | 4.3 | -0.3 | -0.06 | — | — |
| e5_long_prose_en | sleep_30d | bullets | V2 | 3 | 3.7 | 4.3 | -0.7 | -0.12 | — | — (n=0) / -0.7 (n=3) |
| e5_no_questions_en | garden_30d | ends_with_question | B1 | 3 | 1.0 | 0.0 | 1.0 | — | — | — |
| e5_no_questions_en | garden_30d | ends_with_question | B2 | 3 | 0.7 | 0.0 | 0.7 | 1.63 | — | — |
| e5_no_questions_en | garden_30d | ends_with_question | B3 | 3 | 0.3 | 0.0 | 0.3 | 0.82 | — | — |
| e5_no_questions_en | garden_30d | ends_with_question | V1 | 3 | 0.3 | 0.0 | 0.3 | 0.82 | — | — |
| e5_no_questions_en | garden_30d | ends_with_question | V2 | 3 | 0.0 | 0.0 | 0.0 | — | — | 0.0 (n=3) / — (n=0) |
| e5_no_questions_en | programming_7d | ends_with_question | B1 | 3 | 0.7 | 0.3 | 0.3 | 0.58 | — | — |
| e5_no_questions_en | programming_7d | ends_with_question | B2 | 3 | 0.7 | 0.3 | 0.3 | 0.58 | — | — |
| e5_no_questions_en | programming_7d | ends_with_question | B3 | 3 | 1.0 | 0.3 | 0.7 | 1.63 | — | — |
| e5_no_questions_en | programming_7d | ends_with_question | V1 | 3 | 1.0 | 0.3 | 0.7 | 1.63 | — | — |
| e5_no_questions_en | programming_7d | ends_with_question | V2 | 3 | 0.3 | 0.3 | 0.0 | 0.00 | — | 0.0 (n=3) / — (n=0) |
| e5_no_questions_en | programming_7d_no_lessons | ends_with_question | B1 | 3 | 0.7 | 0.3 | 0.3 | 0.58 | — | — |
| e5_no_questions_en | programming_7d_no_lessons | ends_with_question | B2 | 3 | 0.7 | 0.3 | 0.3 | 0.58 | — | — |
| e5_no_questions_en | programming_7d_no_lessons | ends_with_question | B3 | 3 | 0.3 | 0.3 | 0.0 | 0.00 | — | — |
| e5_no_questions_en | programming_7d_no_lessons | ends_with_question | V1 | 3 | 0.7 | 0.3 | 0.3 | 0.58 | — | — |
| e5_no_questions_en | programming_7d_no_lessons | ends_with_question | V2 | 3 | 0.7 | 0.3 | 0.3 | 0.58 | — | — (n=0) / 0.3 (n=3) |
| e5_no_questions_en | sleep_1d | ends_with_question | B1 | 3 | 0.7 | 0.7 | 0.0 | 0.00 | — | — |
| e5_no_questions_en | sleep_1d | ends_with_question | B2 | 3 | 0.7 | 0.7 | 0.0 | 0.00 | — | — |
| e5_no_questions_en | sleep_1d | ends_with_question | B3 | 3 | 0.0 | 0.7 | -0.7 | -1.63 | — | — |
| e5_no_questions_en | sleep_1d | ends_with_question | V1 | 3 | 0.7 | 0.7 | 0.0 | 0.00 | — | — |
| e5_no_questions_en | sleep_1d | ends_with_question | V2 | 3 | 0.3 | 0.7 | -0.3 | -0.58 | — | -0.3 (n=3) / — (n=0) |
| e5_prose_en | garden_30d | bullets | B1 | 3 | 17.3 | 10.0 | 7.3 | 1.11 | — | — |
| e5_prose_en | garden_30d | bullets | B2 | 3 | 14.0 | 10.0 | 4.0 | 0.56 | — | — |
| e5_prose_en | garden_30d | bullets | B3 | 3 | 6.3 | 10.0 | -3.7 | -0.59 | — | — |
| e5_prose_en | garden_30d | bullets | V1 | 3 | 10.3 | 10.0 | 0.3 | 0.05 | — | — |
| e5_prose_en | garden_30d | bullets | V2 | 3 | 3.3 | 10.0 | -6.7 | -1.09 | — | -6.7 (n=3) / — (n=0) |
| e5_prose_en | programming_7d | bullets | B1 | 3 | 17.7 | 9.7 | 8.0 | 2.43 | — | — |
| e5_prose_en | programming_7d | bullets | B2 | 3 | 15.0 | 9.7 | 5.3 | 0.92 | — | — |
| e5_prose_en | programming_7d | bullets | B3 | 3 | 6.3 | 9.7 | -3.3 | -2.18 | — | — |
| e5_prose_en | programming_7d | bullets | V1 | 3 | 2.3 | 9.7 | -7.3 | -3.52 | — | — |
| e5_prose_en | programming_7d | bullets | V2 | 3 | 3.0 | 9.7 | -6.7 | -4.53 | — | -6.7 (n=3) / — (n=0) |
| e5_prose_en | programming_7d_false_belief | bullets | B1 | 3 | 16.7 | 9.3 | 7.3 | 2.54 | — | — |
| e5_prose_en | programming_7d_false_belief | bullets | B2 | 3 | 12.3 | 9.3 | 3.0 | 0.47 | — | — |
| e5_prose_en | programming_7d_false_belief | bullets | B3 | 3 | 6.7 | 9.3 | -2.7 | -0.92 | — | — |
| e5_prose_en | programming_7d_false_belief | bullets | V1 | 3 | 7.0 | 9.3 | -2.3 | -0.58 | — | — |
| e5_prose_en | programming_7d_false_belief | bullets | V2 | 3 | 3.7 | 9.3 | -5.7 | -1.91 | — | -5.7 (n=3) / — (n=0) |
| e5_prose_en | programming_7d_no_lessons | bullets | B1 | 3 | 22.3 | 9.3 | 13.0 | 2.25 | — | — |
| e5_prose_en | programming_7d_no_lessons | bullets | B2 | 3 | 14.3 | 9.3 | 5.0 | 0.81 | — | — |
| e5_prose_en | programming_7d_no_lessons | bullets | B3 | 3 | 6.7 | 9.3 | -2.7 | -0.55 | — | — |
| e5_prose_en | programming_7d_no_lessons | bullets | V1 | 3 | 4.7 | 9.3 | -4.7 | -0.78 | — | — |
| e5_prose_en | programming_7d_no_lessons | bullets | V2 | 3 | 3.7 | 9.3 | -5.7 | -1.16 | — | — (n=0) / -5.7 (n=3) |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | bullets | B1 | 3 | 20.0 | 8.3 | 11.7 | 1.81 | — | — |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | bullets | B2 | 3 | 13.3 | 8.3 | 5.0 | 1.01 | — | — |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | bullets | B3 | 3 | 6.7 | 8.3 | -1.7 | -0.40 | — | — |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | bullets | V1 | 3 | 6.7 | 8.3 | -1.7 | -0.31 | — | — |
| e5_prose_en | programming_7d_no_lessons_no_selfmodel | bullets | V2 | 3 | 9.3 | 8.3 | 1.0 | 0.13 | — | — (n=0) / 1.0 (n=3) |
| e5_prose_en | programming_7d_no_selfmodel | bullets | B1 | 3 | 20.7 | 9.3 | 11.3 | 3.61 | — | — |
| e5_prose_en | programming_7d_no_selfmodel | bullets | B2 | 3 | 16.7 | 9.3 | 7.3 | 1.76 | — | — |
| e5_prose_en | programming_7d_no_selfmodel | bullets | B3 | 3 | 6.7 | 9.3 | -2.7 | -0.90 | — | — |
| e5_prose_en | programming_7d_no_selfmodel | bullets | V1 | 3 | 8.0 | 9.3 | -1.3 | -0.26 | — | — |
| e5_prose_en | programming_7d_no_selfmodel | bullets | V2 | 3 | 3.0 | 9.3 | -6.3 | -2.15 | — | -6.3 (n=3) / — (n=0) |
| e5_prose_en | sleep_1d | bullets | B1 | 3 | 14.7 | 4.7 | 10.0 | 1.60 | — | — |
| e5_prose_en | sleep_1d | bullets | B2 | 3 | 4.7 | 4.7 | 0.0 | 0.00 | — | — |
| e5_prose_en | sleep_1d | bullets | B3 | 3 | 6.3 | 4.7 | 1.7 | 0.29 | — | — |
| e5_prose_en | sleep_1d | bullets | V1 | 3 | 8.3 | 4.7 | 3.7 | 0.62 | — | — |
| e5_prose_en | sleep_1d | bullets | V2 | 3 | 3.0 | 4.7 | -1.7 | -0.29 | — | -1.7 (n=3) / — (n=0) |
| e5_short_en | garden_30d | words | B1 | 3 | 477.7 | 264.0 | 213.7 | 6.30 | — | — |
| e5_short_en | garden_30d | words | B2 | 3 | 309.7 | 264.0 | 45.7 | 0.89 | — | — |
| e5_short_en | garden_30d | words | B3 | 3 | 116.7 | 264.0 | -147.3 | -6.25 | — | — |
| e5_short_en | garden_30d | words | V1 | 3 | 257.0 | 264.0 | -7.0 | -0.22 | — | — |
| e5_short_en | garden_30d | words | V2 | 3 | 149.7 | 264.0 | -114.3 | -4.80 | — | -114.3 (n=3) / — (n=0) |
| e5_short_en | programming_7d | words | B1 | 3 | 466.7 | 230.0 | 236.7 | 8.19 | — | — |
| e5_short_en | programming_7d | words | B2 | 3 | 340.0 | 230.0 | 110.0 | 2.80 | — | — |
| e5_short_en | programming_7d | words | B3 | 3 | 94.3 | 230.0 | -135.7 | -6.29 | — | — |
| e5_short_en | programming_7d | words | V1 | 3 | 254.0 | 230.0 | 24.0 | 0.58 | — | — |
| e5_short_en | programming_7d | words | V2 | 3 | 139.7 | 230.0 | -90.3 | -4.10 | — | -90.3 (n=3) / — (n=0) |
| e5_short_en | programming_7d_no_lessons | words | B1 | 3 | 498.3 | — | — | — | — | — |
| e5_short_en | programming_7d_no_lessons | words | B2 | 3 | 305.7 | — | — | — | — | — |
| e5_short_en | programming_7d_no_lessons | words | B3 | 3 | 102.7 | — | — | — | — | — |
| e5_short_en | programming_7d_no_lessons | words | V1 | 3 | 238.7 | — | — | — | — | — |
| e5_short_en | programming_7d_no_lessons | words | V2 | 3 | 104.0 | — | — | — | — | — (n=0) / — (n=3) |
| e5_short_en | sleep_1d | words | B1 | 3 | 458.3 | 261.0 | 197.3 | 2.66 | — | — |
| e5_short_en | sleep_1d | words | B2 | 3 | 333.3 | 261.0 | 72.3 | 1.94 | — | — |
| e5_short_en | sleep_1d | words | B3 | 3 | 123.0 | 261.0 | -138.0 | -3.81 | — | — |
| e5_short_en | sleep_1d | words | V1 | 3 | 241.3 | 261.0 | -19.7 | -0.46 | — | — |
| e5_short_en | sleep_1d | words | V2 | 3 | 105.3 | 261.0 | -155.7 | -4.55 | — | -155.7 (n=3) / — (n=0) |
| e6_prose_then_lists_en | after_phase1 | bullets | B1 | 3 | 11.7 | 4.0 | 7.7 | 1.47 | — | — |
| e6_prose_then_lists_en | after_phase1 | bullets | B2 | 3 | 4.7 | 4.0 | 0.7 | 0.09 | — | — |
| e6_prose_then_lists_en | after_phase1 | bullets | B3 | 3 | 7.3 | 4.0 | 3.3 | 0.66 | — | — |
| e6_prose_then_lists_en | after_phase1 | bullets | V1 | 3 | 5.0 | 4.0 | 1.0 | 0.17 | — | — |
| e6_prose_then_lists_en | after_phase1 | bullets | V2 | 3 | 5.0 | 4.0 | 1.0 | 0.20 | — | 1.0 (n=3) / — (n=0) |
| e6_prose_then_lists_en | phase2_2 | bullets | B1 | 3 | 18.3 | 9.7 | 8.7 | 2.92 | — | — |
| e6_prose_then_lists_en | phase2_2 | bullets | B2 | 3 | 15.3 | 9.7 | 5.7 | 1.00 | — | — |
| e6_prose_then_lists_en | phase2_2 | bullets | B3 | 3 | 7.7 | 9.7 | -2.0 | -0.67 | — | — |
| e6_prose_then_lists_en | phase2_2 | bullets | V1 | 3 | 9.0 | 9.7 | -0.7 | -0.16 | — | — |
| e6_prose_then_lists_en | phase2_2 | bullets | V2 | 3 | 15.0 | 9.7 | 5.3 | 1.76 | — | 5.3 (n=3) / — (n=0) |
| e6_prose_then_lists_en | phase2_4 | bullets | B1 | 3 | 18.0 | 12.3 | 5.7 | 1.12 | — | — |
| e6_prose_then_lists_en | phase2_4 | bullets | B2 | 3 | 12.3 | 12.3 | 0.0 | 0.00 | — | — |
| e6_prose_then_lists_en | phase2_4 | bullets | B3 | 3 | 6.7 | 12.3 | -5.7 | -1.15 | — | — |
| e6_prose_then_lists_en | phase2_4 | bullets | V1 | 3 | 8.3 | 12.3 | -4.0 | -0.58 | — | — |
| e6_prose_then_lists_en | phase2_4 | bullets | V2 | 3 | 15.3 | 12.3 | 3.0 | 0.52 | — | 3.0 (n=3) / — (n=0) |
| e6_prose_then_lists_en | phase2_6 | bullets | B1 | 3 | 18.7 | 11.7 | 7.0 | 1.29 | — | — |
| e6_prose_then_lists_en | phase2_6 | bullets | B2 | 3 | 12.7 | 11.7 | 1.0 | 0.22 | — | — |
| e6_prose_then_lists_en | phase2_6 | bullets | B3 | 3 | 5.0 | 11.7 | -6.7 | -1.43 | — | — |
| e6_prose_then_lists_en | phase2_6 | bullets | V1 | 3 | 7.3 | 11.7 | -4.3 | -0.76 | — | — |
| e6_prose_then_lists_en | phase2_6 | bullets | V2 | 3 | 15.3 | 11.7 | 3.7 | 0.94 | — | 3.7 (n=3) / — (n=0) |
| e6_short_then_long_en | after_phase1 | words | B1 | 3 | 423.0 | 287.7 | 135.3 | 4.24 | — | — |
| e6_short_then_long_en | after_phase1 | words | B2 | 3 | 318.0 | 287.7 | 30.3 | 0.92 | — | — |
| e6_short_then_long_en | after_phase1 | words | B3 | 3 | 278.0 | 287.7 | -9.7 | -0.18 | — | — |
| e6_short_then_long_en | after_phase1 | words | V1 | 3 | 223.7 | 287.7 | -64.0 | -1.53 | — | — |
| e6_short_then_long_en | after_phase1 | words | V2 | 3 | 93.7 | 287.7 | -194.0 | -5.86 | — | -194.0 (n=3) / — (n=0) |
| e6_short_then_long_en | phase2_2 | words | B1 | 3 | 463.7 | 264.0 | 199.7 | 5.08 | — | — |
| e6_short_then_long_en | phase2_2 | words | B2 | 3 | 262.7 | 264.0 | -1.3 | -0.03 | — | — |
| e6_short_then_long_en | phase2_2 | words | B3 | 3 | 265.0 | 264.0 | 1.0 | 0.03 | — | — |
| e6_short_then_long_en | phase2_2 | words | V1 | 3 | 247.3 | 264.0 | -16.7 | -0.43 | — | — |
| e6_short_then_long_en | phase2_2 | words | V2 | 3 | 8.7 | 264.0 | -255.3 | -6.92 | — | -255.3 (n=3) / — (n=0) |
| e6_short_then_long_en | phase2_4 | words | B1 | 3 | 529.3 | 268.3 | 261.0 | 4.52 | — | — |
| e6_short_then_long_en | phase2_4 | words | B2 | 3 | 310.3 | 268.3 | 42.0 | 2.27 | — | — |
| e6_short_then_long_en | phase2_4 | words | B3 | 3 | 314.0 | 268.3 | 45.7 | 3.18 | — | — |
| e6_short_then_long_en | phase2_4 | words | V1 | 3 | 264.7 | 268.3 | -3.7 | -0.27 | — | — |
| e6_short_then_long_en | phase2_4 | words | V2 | 3 | 175.7 | 268.3 | -92.7 | -6.86 | — | -92.7 (n=3) / — (n=0) |
| e6_short_then_long_en | phase2_6 | words | B1 | 3 | 549.7 | 259.0 | 290.7 | 9.04 | — | — |
| e6_short_then_long_en | phase2_6 | words | B2 | 3 | 262.0 | 259.0 | 3.0 | 0.11 | — | — |
| e6_short_then_long_en | phase2_6 | words | B3 | 3 | 319.3 | 259.0 | 60.3 | 1.68 | — | — |
| e6_short_then_long_en | phase2_6 | words | V1 | 3 | 275.0 | 259.0 | 16.0 | 0.41 | — | — |
| e6_short_then_long_en | phase2_6 | words | V2 | 3 | 160.7 | 259.0 | -98.3 | -2.56 | — | -98.3 (n=3) / — (n=0) |
| e7_venting_en | grandmother_25d | words | B1 | 1 | 92.0 | 92.0 | 0.0 | — | — | — |
| e7_venting_en | grandmother_25d | words | B2 | 1 | 61.0 | 92.0 | -31.0 | — | — | — |
| e7_venting_en | grandmother_25d | words | B3 | 1 | 45.0 | 92.0 | -47.0 | — | — | — |
| e7_venting_en | grandmother_25d | words | V1 | 1 | 76.0 | 92.0 | -16.0 | — | — | — |
| e7_venting_en | grandmother_25d | words | V2 | 1 | 117.0 | 92.0 | 25.0 | — | — | — (n=0) / 25.0 (n=1) |
| e7_venting_en | grandmother_25d_no_lessons | words | B1 | 1 | 81.0 | 79.0 | 2.0 | — | — | — |
| e7_venting_en | grandmother_25d_no_lessons | words | B2 | 1 | 74.0 | 79.0 | -5.0 | — | — | — |
| e7_venting_en | grandmother_25d_no_lessons | words | B3 | 1 | 49.0 | 79.0 | -30.0 | — | — | — |
| e7_venting_en | grandmother_25d_no_lessons | words | V1 | 1 | 75.0 | 79.0 | -4.0 | — | — | — |
| e7_venting_en | grandmother_25d_no_lessons | words | V2 | 1 | 103.0 | 79.0 | 24.0 | — | — | — (n=0) / 24.0 (n=1) |

## Learning curves (key sessions, mean measure of the agent's replies)

| scenario | measure | cond | n | s1 | s2 | s3 | s4 | s5 | s6 | s7 | s8 | s9 | s10 | s11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e5_emoji_en | emoji | B0 | 1 | 0.0 | 0.0 | 0.2 | 0.0 | 0.0 | 0.0 | — | — | — | — | — |
| e5_emoji_en | emoji | B1 | 1 | 0.2 | 0.0 | 0.2 | 1.0 | 0.2 | 0.8 | — | — | — | — | — |
| e5_emoji_en | emoji | B2 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.8 | — | — | — | — | — |
| e5_emoji_en | emoji | B3 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | — | — | — |
| e5_emoji_en | emoji | V1 | 1 | 0.0 | 0.2 | 0.0 | 0.0 | 0.0 | 0.2 | — | — | — | — | — |
| e5_emoji_en | emoji | V2 | 1 | 0.8 | 0.2 | 0.2 | 0.5 | 1.0 | 1.5 | — | — | — | — | — |
| e5_long_prose_en | bullets | B0 | 1 | 4.5 | 3.5 | 3.5 | 9.0 | 0.0 | 5.0 | — | — | — | — | — |
| e5_long_prose_en | bullets | B1 | 1 | 4.0 | 3.5 | 1.5 | 9.5 | 0.0 | 5.5 | — | — | — | — | — |
| e5_long_prose_en | bullets | B2 | 1 | 4.0 | 3.5 | 5.0 | 6.5 | 0.0 | 4.5 | — | — | — | — | — |
| e5_long_prose_en | bullets | B3 | 1 | 4.0 | 3.0 | 3.5 | 3.5 | 2.5 | 3.0 | — | — | — | — | — |
| e5_long_prose_en | bullets | V1 | 1 | 3.5 | 2.5 | 1.0 | 2.0 | 2.5 | 5.0 | — | — | — | — | — |
| e5_long_prose_en | bullets | V2 | 1 | 3.5 | 3.0 | 3.5 | 1.5 | 1.5 | 1.5 | — | — | — | — | — |
| e5_no_questions_en | ends_with_question | B0 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5 | 0.5 | — | — | — | — | — |
| e5_no_questions_en | ends_with_question | B1 | 1 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | — | — | — | — | — |
| e5_no_questions_en | ends_with_question | B2 | 1 | 0.8 | 0.0 | 0.0 | 0.5 | 0.2 | 0.2 | — | — | — | — | — |
| e5_no_questions_en | ends_with_question | B3 | 1 | 0.5 | 0.0 | 0.0 | 0.0 | 0.2 | 0.0 | — | — | — | — | — |
| e5_no_questions_en | ends_with_question | V1 | 1 | 0.0 | 1.0 | 0.8 | 0.5 | 0.5 | 0.5 | — | — | — | — | — |
| e5_no_questions_en | ends_with_question | V2 | 1 | 0.8 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | — | — | — | — | — |
| e5_prose_en | bullets | B0 | 1 | 5.5 | 4.0 | 7.0 | 3.2 | 0.0 | 7.2 | — | — | — | — | — |
| e5_prose_en | bullets | B1 | 1 | 6.2 | 4.2 | 8.5 | 8.8 | 6.5 | 7.0 | — | — | — | — | — |
| e5_prose_en | bullets | B2 | 1 | 7.5 | 3.2 | 5.8 | 6.8 | 0.0 | 10.5 | — | — | — | — | — |
| e5_prose_en | bullets | B3 | 1 | 6.5 | 2.8 | 5.0 | 3.5 | 3.0 | 3.2 | — | — | — | — | — |
| e5_prose_en | bullets | V1 | 1 | 6.5 | 4.0 | 5.8 | 6.0 | 2.5 | 3.0 | — | — | — | — | — |
| e5_prose_en | bullets | V2 | 1 | 6.0 | 2.5 | 2.8 | 1.5 | 1.8 | 1.5 | — | — | — | — | — |
| e5_short_en | words | B0 | 1 | 167.5 | 185.8 | 154.2 | 149.8 | 111.2 | 131.0 | — | — | — | — | — |
| e5_short_en | words | B1 | 1 | 165.2 | 206.2 | 203.2 | 220.2 | 203.2 | 242.8 | — | — | — | — | — |
| e5_short_en | words | B2 | 1 | 241.0 | 218.2 | 177.2 | 172.2 | 193.5 | 146.0 | — | — | — | — | — |
| e5_short_en | words | B3 | 1 | 159.5 | 45.0 | 53.5 | 62.2 | 54.8 | 63.0 | — | — | — | — | — |
| e5_short_en | words | V1 | 1 | 164.5 | 187.8 | 155.2 | 148.0 | 118.2 | 143.5 | — | — | — | — | — |
| e5_short_en | words | V2 | 1 | 161.8 | 45.8 | 55.5 | 50.8 | 54.8 | 75.0 | — | — | — | — | — |
| e6_prose_then_lists_en | bullets | B0 | 1 | 6.2 | 3.2 | 6.2 | 8.8 | 0.0 | 3.8 | 5.2 | 2.8 | 0.0 | 9.2 | 2.2 |
| e6_prose_then_lists_en | bullets | B1 | 1 | 6.2 | 4.0 | 7.8 | 7.2 | 5.2 | 8.5 | 7.2 | 6.2 | 4.8 | 12.8 | 5.0 |
| e6_prose_then_lists_en | bullets | B2 | 1 | 6.5 | 3.2 | 7.5 | 6.8 | 3.0 | 5.2 | 7.0 | 4.5 | 0.0 | 8.5 | 2.5 |
| e6_prose_then_lists_en | bullets | B3 | 1 | 8.0 | 2.5 | 4.2 | 1.8 | 3.2 | 3.5 | 3.8 | 2.8 | 2.8 | 9.0 | 0.0 |
| e6_prose_then_lists_en | bullets | V1 | 1 | 6.0 | 4.2 | 6.5 | 4.5 | 0.0 | 6.5 | 5.2 | 3.8 | 0.0 | 5.0 | 3.5 |
| e6_prose_then_lists_en | bullets | V2 | 1 | 7.5 | 1.0 | 4.2 | 2.5 | 2.5 | 3.0 | 5.5 | 5.5 | 3.8 | 8.8 | 4.8 |
| e6_short_then_long_en | words | B0 | 1 | 188.0 | 152.5 | 153.0 | 150.5 | 121.5 | 121.5 | 142.2 | 100.0 | 169.8 | 149.2 | 151.0 |
| e6_short_then_long_en | words | B1 | 1 | 164.8 | 232.5 | 185.0 | 203.0 | 207.5 | 242.0 | 205.0 | 175.5 | 261.8 | 250.5 | 276.2 |
| e6_short_then_long_en | words | B2 | 1 | 230.8 | 210.5 | 154.2 | 172.5 | 146.2 | 162.8 | 152.5 | 128.8 | 163.5 | 143.5 | 175.8 |
| e6_short_then_long_en | words | B3 | 1 | 174.8 | 143.5 | 86.8 | 132.0 | 122.8 | 163.8 | 137.8 | 136.0 | 164.2 | 141.2 | 177.2 |
| e6_short_then_long_en | words | V1 | 1 | 182.8 | 173.2 | 165.0 | 179.2 | 188.5 | 183.8 | 154.2 | 97.5 | 156.5 | 142.0 | 156.0 |
| e6_short_then_long_en | words | V2 | 1 | 170.5 | 34.2 | 28.5 | 46.0 | 52.0 | 41.5 | 20.2 | 33.5 | 75.5 | 64.5 | 71.0 |
| e7_venting_en | words | B0 | 1 | 85.3 | — | — | — | — | — | — | — | — | — | — |
| e7_venting_en | words | B1 | 1 | 77.3 | — | — | — | — | — | — | — | — | — | — |
| e7_venting_en | words | B2 | 1 | 86.7 | — | — | — | — | — | — | — | — | — | — |
| e7_venting_en | words | B3 | 1 | 79.3 | — | — | — | — | — | — | — | — | — | — |
| e7_venting_en | words | V1 | 1 | 62.0 | — | — | — | — | — | — | — | — | — | — |
| e7_venting_en | words | V2 | 1 | 59.3 | — | — | — | — | — | — | — | — | — | — |

## Self-report vs behavior

Claim = judge score of the self-report; behavior = pass rate of the paired probe's checks; divergence = mean |claim − behavior| over runs.

| scenario | self-report | paired probe | cond | n | claim | behavior | divergence |
|---|---|---|---|---|---|---|---|
| e5_prose_en | programming_7d_false_belief_says | programming_7d_false_belief | B0 | 1 | 1.00 | 0.00 | 1.00 |
| e5_prose_en | programming_7d_false_belief_says | programming_7d_false_belief | B1 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_false_belief_says | programming_7d_false_belief | B2 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_false_belief_says | programming_7d_false_belief | B3 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_false_belief_says | programming_7d_false_belief | V1 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_false_belief_says | programming_7d_false_belief | V2 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_says | programming_7d | B0 | 1 | 1.00 | 0.00 | 1.00 |
| e5_prose_en | programming_7d_says | programming_7d | B1 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_says | programming_7d | B2 | 1 | 1.00 | 0.00 | 1.00 |
| e5_prose_en | programming_7d_says | programming_7d | B3 | 1 | 0.00 | 0.00 | 0.00 |
| e5_prose_en | programming_7d_says | programming_7d | V1 | 1 | 0.00 | 0.33 | 0.33 |
| e5_prose_en | programming_7d_says | programming_7d | V2 | 1 | 0.50 | 0.00 | 0.50 |
| e5_short_en | programming_7d_says | programming_7d | B0 | 1 | — | 0.00 | — |
| e5_short_en | programming_7d_says | programming_7d | B1 | 1 | 0.00 | 0.00 | 0.00 |
| e5_short_en | programming_7d_says | programming_7d | B2 | 1 | 0.00 | 0.00 | 0.00 |
| e5_short_en | programming_7d_says | programming_7d | B3 | 1 | 1.00 | 1.00 | 0.00 |
| e5_short_en | programming_7d_says | programming_7d | V1 | 1 | 0.00 | 0.00 | 0.00 |
| e5_short_en | programming_7d_says | programming_7d | V2 | 1 | 1.00 | 1.00 | 0.00 |

## V2 state at the end of the run (mean over runs)

| scenario | cond | n | reactions | habits | active lessons | retired | adds | reinforces | weakens | portraits | beliefs grown without evidence | intentions done / dropped / open | chains complete |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e5_emoji_en | V2 | 1 | 18.0 | 1.0 | 5.0 | 1.0 | 6.0 | 8.0 | 1.0 | 6.0 | 0.0 | 2.0 / 0.0 / 0.0 | 1.00 |
| e5_long_prose_en | V2 | 1 | 33.0 | 1.0 | 14.0 | 0.0 | 14.0 | 21.0 | 0.0 | 30.0 | 1.0 | 7.0 / 0.0 / 3.0 | 1.00 |
| e5_no_questions_en | V2 | 1 | 14.0 | 1.0 | 3.0 | 0.0 | 3.0 | 11.0 | 0.0 | 6.0 | 0.0 | 0.0 / 0.0 / 1.0 | 1.00 |
| e5_prose_en | V2 | 1 | 11.0 | 2.0 | 4.0 | 0.0 | 4.0 | 7.0 | 0.0 | 6.0 | 0.0 | 1.0 / 0.0 / 1.0 | 1.00 |
| e5_short_en | V2 | 1 | 15.0 | 1.0 | 2.0 | 1.0 | 3.0 | 11.0 | 2.0 | 6.0 | 0.0 | 2.0 / 0.0 / 1.0 | 1.00 |
| e6_prose_then_lists_en | V2 | 1 | 27.0 | 1.0 | 9.0 | 0.0 | 9.0 | 23.0 | 0.0 | 11.0 | 0.0 | 1.0 / 0.0 / 0.0 | 1.00 |
| e6_short_then_long_en | V2 | 1 | 21.0 | 2.0 | 5.0 | 0.0 | 5.0 | 17.0 | 1.0 | 11.0 | 0.0 | 5.0 / 0.0 / 0.0 | 1.00 |
| e7_reminder_en | V2 | 1 | 5.0 | 0.0 | 4.0 | 0.0 | 4.0 | 2.0 | 0.0 | 4.0 | 0.0 | 3.0 / 0.0 / 1.0 | 1.00 |
| e7_venting_en | V2 | 1 | 12.0 | 0.0 | 4.0 | 0.0 | 4.0 | 4.0 | 0.0 | 9.0 | 0.0 | 2.0 / 0.0 / 0.0 | 1.00 |

## Cost

| cond | runs | mean cost/run $ | total spent $ | est. battery (all scenarios × N=5) $ |
|---|---|---|---|---|
| B0 | 9 | 0.2307 | 2.0764 | 10.38 |
| B1 | 9 | 0.9800 | 8.8197 | 44.10 |
| B2 | 9 | 0.3692 | 3.3232 | 16.62 |
| B3 | 9 | 0.8622 | 7.7601 | 38.80 |
| V1 | 9 | 0.3342 | 3.0079 | 15.04 |
| V2 | 9 | 0.7209 | 6.4880 | 32.44 |

## Judge spot-check

Wrote 19 of 184 judged items to results/raw/v2-pass1/spotcheck.csv (judge scores and conditions hidden). Fill in human_score (0, 0.5, 1) and re-run the report to get agreement.
