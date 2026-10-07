# Report: results/raw/v1-pilot-1

52 runs, conditions: B0, B1, B2, V1

## Scenario × condition (mean ± 95% CI over runs)

| experiment | scenario | cond | n | deterministic pass | judge | recall@prompt | cost/run $ |
|---|---|---|---|---|---|---|---|
| e1 | e1_family_facts_ru | B0 | 1 | 0.20 | 0.20 | — | 0.0339 |
| e1 | e1_family_facts_ru | B1 | 1 | 1.00 | 0.80 | — | 0.0480 |
| e1 | e1_family_facts_ru | B2 | 1 | 1.00 | 1.00 | — | 0.0433 |
| e1 | e1_family_facts_ru | V1 | 1 | 0.80 | 1.00 | 1.00 | 0.0564 |
| e1 | e1_updates_and_abstention_en | B0 | 1 | 0.20 | 0.20 | — | 0.0440 |
| e1 | e1_updates_and_abstention_en | B1 | 1 | 1.00 | 1.00 | — | 0.0636 |
| e1 | e1_updates_and_abstention_en | B2 | 1 | 1.00 | 1.00 | — | 0.0550 |
| e1 | e1_updates_and_abstention_en | V1 | 1 | 1.00 | 1.00 | 1.00 | 0.0674 |
| e1 | e1_work_and_pets_en | B0 | 1 | 0.20 | 0.20 | — | 0.0383 |
| e1 | e1_work_and_pets_en | B1 | 1 | 1.00 | 0.90 | — | 0.0483 |
| e1 | e1_work_and_pets_en | B2 | 1 | 1.00 | 1.00 | — | 0.0478 |
| e1 | e1_work_and_pets_en | V1 | 1 | 1.00 | 0.90 | 1.00 | 0.0590 |
| e2 | e2_first_mention_ru | B0 | 1 | 0.40 | 0.20 | — | 0.0415 |
| e2 | e2_first_mention_ru | B1 | 1 | 1.00 | 0.90 | — | 0.0617 |
| e2 | e2_first_mention_ru | B2 | 1 | 0.80 | 0.90 | — | 0.0595 |
| e2 | e2_first_mention_ru | V1 | 1 | 1.00 | 0.80 | 0.67 | 0.0780 |
| e2 | e2_source_attribution_en | B0 | 1 | 0.25 | 0.10 | — | 0.0435 |
| e2 | e2_source_attribution_en | B1 | 1 | 0.75 | 0.70 | — | 0.0833 |
| e2 | e2_source_attribution_en | B2 | 1 | 0.75 | 0.60 | — | 0.0549 |
| e2 | e2_source_attribution_en | V1 | 1 | 1.00 | 0.80 | 1.00 | 0.0672 |
| e2 | e2_weekly_events_en | B0 | 1 | 0.20 | 0.20 | — | 0.0409 |
| e2 | e2_weekly_events_en | B1 | 1 | 1.00 | 1.00 | — | 0.0586 |
| e2 | e2_weekly_events_en | B2 | 1 | 1.00 | 0.90 | — | 0.0551 |
| e2 | e2_weekly_events_en | V1 | 1 | 1.00 | 0.80 | 1.00 | 0.0659 |
| e3 | e3_exam_nerves_en | B0 | 1 | 0.00 | 0.60 | — | 0.0338 |
| e3 | e3_exam_nerves_en | B1 | 1 | 1.00 | 0.60 | — | 0.0665 |
| e3 | e3_exam_nerves_en | B2 | 1 | 1.00 | 1.00 | — | 0.0448 |
| e3 | e3_exam_nerves_en | V1 | 1 | 1.00 | 0.70 | 1.00 | 0.0550 |
| e3 | e3_health_en | B0 | 1 | 0.00 | 0.60 | — | 0.0452 |
| e3 | e3_health_en | B1 | 1 | 0.50 | 1.00 | — | 0.0500 |
| e3 | e3_health_en | B2 | 1 | 1.00 | 0.60 | — | 0.0532 |
| e3 | e3_health_en | V1 | 1 | 0.50 | 0.80 | 1.00 | 0.0667 |
| e3 | e3_trip_ru | B0 | 1 | 0.50 | 0.70 | — | 0.0561 |
| e3 | e3_trip_ru | B1 | 1 | 1.00 | 0.70 | — | 0.0629 |
| e3 | e3_trip_ru | B2 | 1 | 1.00 | 0.90 | — | 0.0605 |
| e3 | e3_trip_ru | V1 | 1 | 1.00 | 0.90 | 0.75 | 0.0718 |
| e4 | e4_explicit_no_lists_ru | B0 | 1 | 0.00 | 0.00 | — | 0.0671 |
| e4 | e4_explicit_no_lists_ru | B1 | 1 | 1.00 | 1.00 | — | 0.1065 |
| e4 | e4_explicit_no_lists_ru | B2 | 1 | 1.00 | 1.00 | — | 0.0759 |
| e4 | e4_explicit_no_lists_ru | V1 | 1 | 1.00 | 1.00 | 0.00 | 0.0894 |
| e4 | e4_explicit_short_en | B0 | 1 | 0.00 | 0.00 | — | 0.0541 |
| e4 | e4_explicit_short_en | B1 | 1 | 1.00 | 1.00 | — | 0.0414 |
| e4 | e4_explicit_short_en | B2 | 1 | 1.00 | 1.00 | — | 0.0348 |
| e4 | e4_explicit_short_en | V1 | 1 | 1.00 | 1.00 | 1.00 | 0.0430 |
| e4 | e4_implicit_no_lists_ru | B0 | 1 | 0.00 | 0.00 | — | 0.1105 |
| e4 | e4_implicit_no_lists_ru | B1 | 1 | 0.00 | 0.00 | — | 0.2259 |
| e4 | e4_implicit_no_lists_ru | B2 | 1 | 0.00 | 0.00 | — | 0.1394 |
| e4 | e4_implicit_no_lists_ru | V1 | 1 | 0.00 | 0.00 | — | 0.1544 |
| e4 | e4_implicit_short_en | B0 | 1 | 0.00 | 0.25 | — | 0.0876 |
| e4 | e4_implicit_short_en | B1 | 1 | 0.00 | 0.25 | — | 0.1627 |
| e4 | e4_implicit_short_en | B2 | 1 | 0.00 | 0.00 | — | 0.0938 |
| e4 | e4_implicit_short_en | V1 | 1 | 0.00 | 0.00 | — | 0.1131 |

## Experiment × condition (mean of scenario means)

| experiment | cond | scenarios | deterministic pass | judge | recall@prompt |
|---|---|---|---|---|---|
| e1 | B0 | 3 | 0.20 ± 0.00 | 0.20 ± 0.00 | — |
| e1 | B1 | 3 | 1.00 ± 0.00 | 0.90 ± 0.25 | — |
| e1 | B2 | 3 | 1.00 ± 0.00 | 1.00 ± 0.00 | — |
| e1 | V1 | 3 | 0.93 ± 0.29 | 0.97 ± 0.14 | 1.00 ± 0.00 |
| e2 | B0 | 3 | 0.28 ± 0.26 | 0.17 ± 0.14 | — |
| e2 | B1 | 3 | 0.92 ± 0.36 | 0.87 ± 0.38 | — |
| e2 | B2 | 3 | 0.85 ± 0.33 | 0.80 ± 0.43 | — |
| e2 | V1 | 3 | 1.00 ± 0.00 | 0.80 ± 0.00 | 0.89 ± 0.48 |
| e3 | B0 | 3 | 0.17 ± 0.72 | 0.63 ± 0.14 | — |
| e3 | B1 | 3 | 0.83 ± 0.72 | 0.77 ± 0.52 | — |
| e3 | B2 | 3 | 1.00 ± 0.00 | 0.83 ± 0.52 | — |
| e3 | V1 | 3 | 0.83 ± 0.72 | 0.80 ± 0.25 | 0.92 ± 0.36 |
| e4 | B0 | 4 | 0.00 ± 0.00 | 0.06 ± 0.20 | — |
| e4 | B1 | 4 | 0.50 ± 0.92 | 0.56 ± 0.82 | — |
| e4 | B2 | 4 | 0.50 ± 0.92 | 0.50 ± 0.92 | — |
| e4 | V1 | 4 | 0.50 ± 0.92 | 0.50 ± 0.92 | 0.50 ± 6.35 |

## Per probe

| scenario | probe | cond | n | pass rate | judge | gold in prompt | reply words |
|---|---|---|---|---|---|---|---|
| e1_family_facts_ru | abstain_brother_30d | B0 | 1 | 1.00 | 1.00 | — | 17 |
| e1_family_facts_ru | abstain_brother_30d | B1 | 1 | 1.00 | 0.00 | — | 28 |
| e1_family_facts_ru | abstain_brother_30d | B2 | 1 | 1.00 | 1.00 | — | 27 |
| e1_family_facts_ru | abstain_brother_30d | V1 | 1 | 1.00 | 1.00 | — | 30 |
| e1_family_facts_ru | cat_30d | B0 | 1 | 0.00 | 0.00 | — | 21 |
| e1_family_facts_ru | cat_30d | B1 | 1 | 1.00 | 1.00 | — | 14 |
| e1_family_facts_ru | cat_30d | B2 | 1 | 1.00 | 1.00 | — | 13 |
| e1_family_facts_ru | cat_30d | V1 | 1 | 1.00 | 1.00 | 1.00 | 13 |
| e1_family_facts_ru | name_1d | B0 | 1 | 0.00 | 0.00 | — | 28 |
| e1_family_facts_ru | name_1d | B1 | 1 | 1.00 | 1.00 | — | 8 |
| e1_family_facts_ru | name_1d | B2 | 1 | 1.00 | 1.00 | — | 38 |
| e1_family_facts_ru | name_1d | V1 | 1 | 0.00 | 1.00 | 1.00 | 58 |
| e1_family_facts_ru | sister_city_7d | B0 | 1 | 0.00 | 0.00 | — | 19 |
| e1_family_facts_ru | sister_city_7d | B1 | 1 | 1.00 | 1.00 | — | 15 |
| e1_family_facts_ru | sister_city_7d | B2 | 1 | 1.00 | 1.00 | — | 27 |
| e1_family_facts_ru | sister_city_7d | V1 | 1 | 1.00 | 1.00 | 1.00 | 32 |
| e1_family_facts_ru | sister_job_30d | B0 | 1 | 0.00 | 0.00 | — | 22 |
| e1_family_facts_ru | sister_job_30d | B1 | 1 | 1.00 | 1.00 | — | 13 |
| e1_family_facts_ru | sister_job_30d | B2 | 1 | 1.00 | 1.00 | — | 23 |
| e1_family_facts_ru | sister_job_30d | V1 | 1 | 1.00 | 1.00 | 1.00 | 19 |
| e1_updates_and_abstention_en | abstain_wife_30d | B0 | 1 | 1.00 | 1.00 | — | 45 |
| e1_updates_and_abstention_en | abstain_wife_30d | B1 | 1 | 1.00 | 1.00 | — | 65 |
| e1_updates_and_abstention_en | abstain_wife_30d | B2 | 1 | 1.00 | 1.00 | — | 43 |
| e1_updates_and_abstention_en | abstain_wife_30d | V1 | 1 | 1.00 | 1.00 | — | 50 |
| e1_updates_and_abstention_en | diet_30d | B0 | 1 | 0.00 | 0.00 | — | 168 |
| e1_updates_and_abstention_en | diet_30d | B1 | 1 | 1.00 | 1.00 | — | 166 |
| e1_updates_and_abstention_en | diet_30d | B2 | 1 | 1.00 | 1.00 | — | 140 |
| e1_updates_and_abstention_en | diet_30d | V1 | 1 | 1.00 | 1.00 | 1.00 | 120 |
| e1_updates_and_abstention_en | emma_7d | B0 | 1 | 0.00 | 0.00 | — | 56 |
| e1_updates_and_abstention_en | emma_7d | B1 | 1 | 1.00 | 1.00 | — | 79 |
| e1_updates_and_abstention_en | emma_7d | B2 | 1 | 1.00 | 1.00 | — | 100 |
| e1_updates_and_abstention_en | emma_7d | V1 | 1 | 1.00 | 1.00 | 1.00 | 37 |
| e1_updates_and_abstention_en | exercise_30d | B0 | 1 | 0.00 | 0.00 | — | 48 |
| e1_updates_and_abstention_en | exercise_30d | B1 | 1 | 1.00 | 1.00 | — | 12 |
| e1_updates_and_abstention_en | exercise_30d | B2 | 1 | 1.00 | 1.00 | — | 26 |
| e1_updates_and_abstention_en | exercise_30d | V1 | 1 | 1.00 | 1.00 | 1.00 | 22 |
| e1_updates_and_abstention_en | race_1d | B0 | 1 | 0.00 | 0.00 | — | 39 |
| e1_updates_and_abstention_en | race_1d | B1 | 1 | 1.00 | 1.00 | — | 21 |
| e1_updates_and_abstention_en | race_1d | B2 | 1 | 1.00 | 1.00 | — | 43 |
| e1_updates_and_abstention_en | race_1d | V1 | 1 | 1.00 | 1.00 | 1.00 | 49 |
| e1_work_and_pets_en | abstain_salary_30d | B0 | 1 | 1.00 | 1.00 | — | 46 |
| e1_work_and_pets_en | abstain_salary_30d | B1 | 1 | 1.00 | 1.00 | — | 40 |
| e1_work_and_pets_en | abstain_salary_30d | B2 | 1 | 1.00 | 1.00 | — | 58 |
| e1_work_and_pets_en | abstain_salary_30d | V1 | 1 | 1.00 | 1.00 | — | 48 |
| e1_work_and_pets_en | dog_30d | B0 | 1 | 0.00 | 0.00 | — | 49 |
| e1_work_and_pets_en | dog_30d | B1 | 1 | 1.00 | 1.00 | — | 18 |
| e1_work_and_pets_en | dog_30d | B2 | 1 | 1.00 | 1.00 | — | 19 |
| e1_work_and_pets_en | dog_30d | V1 | 1 | 1.00 | 1.00 | 1.00 | 31 |
| e1_work_and_pets_en | job_7d | B0 | 1 | 0.00 | 0.00 | — | 41 |
| e1_work_and_pets_en | job_7d | B1 | 1 | 1.00 | 0.50 | — | 48 |
| e1_work_and_pets_en | job_7d | B2 | 1 | 1.00 | 1.00 | — | 52 |
| e1_work_and_pets_en | job_7d | V1 | 1 | 1.00 | 0.50 | 1.00 | 40 |
| e1_work_and_pets_en | partner_1d | B0 | 1 | 0.00 | 0.00 | — | 40 |
| e1_work_and_pets_en | partner_1d | B1 | 1 | 1.00 | 1.00 | — | 19 |
| e1_work_and_pets_en | partner_1d | B2 | 1 | 1.00 | 1.00 | — | 25 |
| e1_work_and_pets_en | partner_1d | V1 | 1 | 1.00 | 1.00 | 1.00 | 22 |
| e1_work_and_pets_en | start_date_30d | B0 | 1 | 0.00 | 0.00 | — | 54 |
| e1_work_and_pets_en | start_date_30d | B1 | 1 | 1.00 | 1.00 | — | 8 |
| e1_work_and_pets_en | start_date_30d | B2 | 1 | 1.00 | 1.00 | — | 40 |
| e1_work_and_pets_en | start_date_30d | V1 | 1 | 1.00 | 1.00 | 1.00 | 34 |
| e2_first_mention_ru | abstain | B0 | 1 | 1.00 | 1.00 | — | 28 |
| e2_first_mention_ru | abstain | B1 | 1 | 1.00 | 1.00 | — | 36 |
| e2_first_mention_ru | abstain | B2 | 1 | 0.00 | 1.00 | — | 34 |
| e2_first_mention_ru | abstain | V1 | 1 | 1.00 | 1.00 | — | 44 |
| e2_first_mention_ru | first_spanish | B0 | 1 | 0.00 | 0.00 | — | 35 |
| e2_first_mention_ru | first_spanish | B1 | 1 | 1.00 | 1.00 | — | 11 |
| e2_first_mention_ru | first_spanish | B2 | 1 | 1.00 | 1.00 | — | 36 |
| e2_first_mention_ru | first_spanish | V1 | 1 | 1.00 | 0.50 | 0.00 | 29 |
| e2_first_mention_ru | order | B0 | 1 | 1.00 | 0.00 | — | 31 |
| e2_first_mention_ru | order | B1 | 1 | 1.00 | 0.50 | — | 29 |
| e2_first_mention_ru | order | B2 | 1 | 1.00 | 0.50 | — | 19 |
| e2_first_mention_ru | order | V1 | 1 | 1.00 | 1.00 | — | 27 |
| e2_first_mention_ru | source | B0 | 1 | 0.00 | 0.00 | — | 48 |
| e2_first_mention_ru | source | B1 | 1 | 1.00 | 1.00 | — | 25 |
| e2_first_mention_ru | source | B2 | 1 | 1.00 | 1.00 | — | 33 |
| e2_first_mention_ru | source | V1 | 1 | 1.00 | 1.00 | 1.00 | 26 |
| e2_first_mention_ru | yesterday | B0 | 1 | 0.00 | 0.00 | — | 27 |
| e2_first_mention_ru | yesterday | B1 | 1 | 1.00 | 1.00 | — | 29 |
| e2_first_mention_ru | yesterday | B2 | 1 | 1.00 | 1.00 | — | 35 |
| e2_first_mention_ru | yesterday | V1 | 1 | 1.00 | 0.50 | 1.00 | 66 |
| e2_source_attribution_en | abstain | B0 | 1 | 1.00 | 0.50 | — | 43 |
| e2_source_attribution_en | abstain | B1 | 1 | 1.00 | 1.00 | — | 51 |
| e2_source_attribution_en | abstain | B2 | 1 | 1.00 | 1.00 | — | 50 |
| e2_source_attribution_en | abstain | V1 | 1 | 1.00 | 1.00 | — | 53 |
| e2_source_attribution_en | plan_now | B0 | 1 | 0.00 | 0.00 | — | 71 |
| e2_source_attribution_en | plan_now | B1 | 1 | 0.00 | 1.00 | — | 92 |
| e2_source_attribution_en | plan_now | B2 | 1 | 0.00 | 1.00 | — | 86 |
| e2_source_attribution_en | plan_now | V1 | 1 | 1.00 | 1.00 | 1.00 | 59 |
| e2_source_attribution_en | user_said | B0 | 1 | 0.00 | 0.00 | — | 50 |
| e2_source_attribution_en | user_said | B1 | 1 | 1.00 | 1.00 | — | 29 |
| e2_source_attribution_en | user_said | B2 | 1 | 1.00 | 1.00 | — | 16 |
| e2_source_attribution_en | user_said | V1 | 1 | 1.00 | 1.00 | 1.00 | 34 |
| e2_source_attribution_en | when_booked | B0 | 1 | 0.00 | 0.00 | — | 41 |
| e2_source_attribution_en | when_booked | B1 | 1 | 1.00 | 0.50 | — | 10 |
| e2_source_attribution_en | when_booked | B2 | 1 | 1.00 | 0.00 | — | 17 |
| e2_source_attribution_en | when_booked | V1 | 1 | 1.00 | 0.00 | — | 38 |
| e2_source_attribution_en | who_suggested | B0 | 1 | — | 0.00 | — | 52 |
| e2_source_attribution_en | who_suggested | B1 | 1 | — | 0.00 | — | 53 |
| e2_source_attribution_en | who_suggested | B2 | 1 | — | 0.00 | — | 56 |
| e2_source_attribution_en | who_suggested | V1 | 1 | — | 1.00 | — | 82 |
| e2_weekly_events_en | abstain_event | B0 | 1 | 1.00 | 1.00 | — | 45 |
| e2_weekly_events_en | abstain_event | B1 | 1 | 1.00 | 1.00 | — | 51 |
| e2_weekly_events_en | abstain_event | B2 | 1 | 1.00 | 1.00 | — | 60 |
| e2_weekly_events_en | abstain_event | V1 | 1 | 1.00 | 1.00 | — | 75 |
| e2_weekly_events_en | first_pottery | B0 | 1 | 0.00 | 0.00 | — | 53 |
| e2_weekly_events_en | first_pottery | B1 | 1 | 1.00 | 1.00 | — | 37 |
| e2_weekly_events_en | first_pottery | B2 | 1 | 1.00 | 1.00 | — | 42 |
| e2_weekly_events_en | first_pottery | V1 | 1 | 1.00 | 1.00 | 1.00 | 55 |
| e2_weekly_events_en | last_week_topics | B0 | 1 | 0.00 | 0.00 | — | 43 |
| e2_weekly_events_en | last_week_topics | B1 | 1 | 1.00 | 1.00 | — | 94 |
| e2_weekly_events_en | last_week_topics | B2 | 1 | 1.00 | 1.00 | — | 65 |
| e2_weekly_events_en | last_week_topics | V1 | 1 | 1.00 | 0.00 | 1.00 | 113 |
| e2_weekly_events_en | order | B0 | 1 | 0.00 | 0.00 | — | 49 |
| e2_weekly_events_en | order | B1 | 1 | 1.00 | 1.00 | — | 22 |
| e2_weekly_events_en | order | B2 | 1 | 1.00 | 1.00 | — | 25 |
| e2_weekly_events_en | order | V1 | 1 | 1.00 | 1.00 | — | 26 |
| e2_weekly_events_en | saturday | B0 | 1 | 0.00 | 0.00 | — | 34 |
| e2_weekly_events_en | saturday | B1 | 1 | 1.00 | 1.00 | — | 35 |
| e2_weekly_events_en | saturday | B2 | 1 | 1.00 | 0.50 | — | 42 |
| e2_weekly_events_en | saturday | V1 | 1 | 1.00 | 1.00 | 1.00 | 34 |
| e3_exam_nerves_en | after | B0 | 1 | 0.00 | 0.50 | — | 25 |
| e3_exam_nerves_en | after | B1 | 1 | 1.00 | 0.50 | — | 84 |
| e3_exam_nerves_en | after | B2 | 1 | 1.00 | 1.00 | — | 69 |
| e3_exam_nerves_en | after | V1 | 1 | 1.00 | 0.50 | 1.00 | 64 |
| e3_exam_nerves_en | nervous | B0 | 1 | 0.00 | 0.50 | — | 23 |
| e3_exam_nerves_en | nervous | B1 | 1 | 1.00 | 0.75 | — | 126 |
| e3_exam_nerves_en | nervous | B2 | 1 | 1.00 | 1.00 | — | 79 |
| e3_exam_nerves_en | nervous | V1 | 1 | 1.00 | 1.00 | 1.00 | 101 |
| e3_exam_nerves_en | neutral | B0 | 1 | — | 1.00 | — | 162 |
| e3_exam_nerves_en | neutral | B1 | 1 | — | 0.50 | — | 146 |
| e3_exam_nerves_en | neutral | B2 | 1 | — | 1.00 | — | 135 |
| e3_exam_nerves_en | neutral | V1 | 1 | — | 0.50 | — | 160 |
| e3_health_en | moving | B0 | 1 | 0.00 | 0.50 | — | 158 |
| e3_health_en | moving | B1 | 1 | 1.00 | 1.00 | — | 141 |
| e3_health_en | moving | B2 | 1 | 1.00 | 1.00 | — | 121 |
| e3_health_en | moving | V1 | 1 | 1.00 | 0.75 | 1.00 | 150 |
| e3_health_en | neutral | B0 | 1 | — | 1.00 | — | 184 |
| e3_health_en | neutral | B1 | 1 | — | 1.00 | — | 116 |
| e3_health_en | neutral | B2 | 1 | — | 0.00 | — | 182 |
| e3_health_en | neutral | V1 | 1 | — | 0.50 | — | 132 |
| e3_health_en | workout | B0 | 1 | 0.00 | 0.50 | — | 271 |
| e3_health_en | workout | B1 | 1 | 0.00 | 1.00 | — | 216 |
| e3_health_en | workout | B2 | 1 | 1.00 | 0.50 | — | 288 |
| e3_health_en | workout | V1 | 1 | 0.00 | 1.00 | 1.00 | 227 |
| e3_trip_ru | indirect | B0 | 1 | 1.00 | 0.50 | — | 174 |
| e3_trip_ru | indirect | B1 | 1 | 1.00 | 1.00 | — | 155 |
| e3_trip_ru | indirect | B2 | 1 | 1.00 | 1.00 | — | 172 |
| e3_trip_ru | indirect | V1 | 1 | 1.00 | 1.00 | 1.00 | 181 |
| e3_trip_ru | neutral | B0 | 1 | — | 1.00 | — | 91 |
| e3_trip_ru | neutral | B1 | 1 | — | 0.50 | — | 102 |
| e3_trip_ru | neutral | B2 | 1 | — | 0.50 | — | 123 |
| e3_trip_ru | neutral | V1 | 1 | — | 0.50 | — | 127 |
| e3_trip_ru | packing | B0 | 1 | 0.00 | 0.75 | — | 188 |
| e3_trip_ru | packing | B1 | 1 | 1.00 | 0.50 | — | 205 |
| e3_trip_ru | packing | B2 | 1 | 1.00 | 1.00 | — | 208 |
| e3_trip_ru | packing | V1 | 1 | 1.00 | 1.00 | 1.00 | 265 |
| e4_explicit_no_lists_ru | novel_topic | B0 | 1 | 0.00 | 0.00 | — | 171 |
| e4_explicit_no_lists_ru | novel_topic | B1 | 1 | 1.00 | 1.00 | — | 237 |
| e4_explicit_no_lists_ru | novel_topic | B2 | 1 | 1.00 | 1.00 | — | 247 |
| e4_explicit_no_lists_ru | novel_topic | V1 | 1 | 1.00 | 1.00 | 0.00 | 213 |
| e4_explicit_no_lists_ru | novel_topic_2 | B0 | 1 | 0.00 | 0.00 | — | 169 |
| e4_explicit_no_lists_ru | novel_topic_2 | B1 | 1 | 1.00 | 1.00 | — | 270 |
| e4_explicit_no_lists_ru | novel_topic_2 | B2 | 1 | 1.00 | 1.00 | — | 248 |
| e4_explicit_no_lists_ru | novel_topic_2 | V1 | 1 | 1.00 | 1.00 | 0.00 | 239 |
| e4_explicit_short_en | novel_topic | B0 | 1 | 0.00 | 0.00 | — | 344 |
| e4_explicit_short_en | novel_topic | B1 | 1 | 1.00 | 1.00 | — | 45 |
| e4_explicit_short_en | novel_topic | B2 | 1 | 1.00 | 1.00 | — | 47 |
| e4_explicit_short_en | novel_topic | V1 | 1 | 1.00 | 1.00 | 1.00 | 42 |
| e4_explicit_short_en | novel_topic_2 | B0 | 1 | 0.00 | 0.00 | — | 249 |
| e4_explicit_short_en | novel_topic_2 | B1 | 1 | 1.00 | 1.00 | — | 48 |
| e4_explicit_short_en | novel_topic_2 | B2 | 1 | 1.00 | 1.00 | — | 47 |
| e4_explicit_short_en | novel_topic_2 | V1 | 1 | 1.00 | 1.00 | 1.00 | 46 |
| e4_implicit_no_lists_ru | novel_topic | B0 | 1 | 0.00 | 0.00 | — | 176 |
| e4_implicit_no_lists_ru | novel_topic | B1 | 1 | 0.00 | 0.00 | — | 304 |
| e4_implicit_no_lists_ru | novel_topic | B2 | 1 | 0.00 | 0.00 | — | 226 |
| e4_implicit_no_lists_ru | novel_topic | V1 | 1 | 0.00 | 0.00 | — | 191 |
| e4_implicit_no_lists_ru | novel_topic_2 | B0 | 1 | 0.00 | 0.00 | — | 214 |
| e4_implicit_no_lists_ru | novel_topic_2 | B1 | 1 | 0.00 | 0.00 | — | 288 |
| e4_implicit_no_lists_ru | novel_topic_2 | B2 | 1 | 0.00 | 0.00 | — | 282 |
| e4_implicit_no_lists_ru | novel_topic_2 | V1 | 1 | 0.00 | 0.00 | — | 223 |
| e4_implicit_short_en | novel_topic | B0 | 1 | 0.00 | 0.50 | — | 376 |
| e4_implicit_short_en | novel_topic | B1 | 1 | 0.00 | 0.00 | — | 358 |
| e4_implicit_short_en | novel_topic | B2 | 1 | 0.00 | 0.00 | — | 294 |
| e4_implicit_short_en | novel_topic | V1 | 1 | 0.00 | 0.00 | — | 298 |
| e4_implicit_short_en | novel_topic_2 | B0 | 1 | 0.00 | 0.00 | — | 285 |
| e4_implicit_short_en | novel_topic_2 | B1 | 1 | 0.00 | 0.50 | — | 297 |
| e4_implicit_short_en | novel_topic_2 | B2 | 1 | 0.00 | 0.00 | — | 257 |
| e4_implicit_short_en | novel_topic_2 | V1 | 1 | 0.00 | 0.00 | — | 215 |

## E4: behavioral measure vs B0

Effect = mean(condition) − mean(B0); d = Cohen's d. For V1 the effect is also split by whether any gold (originating) memory was in the prompt for the probe reply.

| scenario | probe | measure | cond | n | mean | B0 mean | effect | d | effect (in prompt / not) |
|---|---|---|---|---|---|---|---|---|---|
| e4_explicit_no_lists_ru | novel_topic | bullets | B1 | 1 | 0.0 | 10.0 | -10.0 | — | — |
| e4_explicit_no_lists_ru | novel_topic | bullets | B2 | 1 | 0.0 | 10.0 | -10.0 | — | — |
| e4_explicit_no_lists_ru | novel_topic | bullets | V1 | 1 | 0.0 | 10.0 | -10.0 | — | — (n=0) / -10.0 (n=1) |
| e4_explicit_no_lists_ru | novel_topic_2 | bullets | B1 | 1 | 0.0 | 13.0 | -13.0 | — | — |
| e4_explicit_no_lists_ru | novel_topic_2 | bullets | B2 | 1 | 0.0 | 13.0 | -13.0 | — | — |
| e4_explicit_no_lists_ru | novel_topic_2 | bullets | V1 | 1 | 0.0 | 13.0 | -13.0 | — | — (n=0) / -13.0 (n=1) |
| e4_explicit_short_en | novel_topic | words | B1 | 1 | 45.0 | 344.0 | -299.0 | — | — |
| e4_explicit_short_en | novel_topic | words | B2 | 1 | 47.0 | 344.0 | -297.0 | — | — |
| e4_explicit_short_en | novel_topic | words | V1 | 1 | 42.0 | 344.0 | -302.0 | — | -302.0 (n=1) / — (n=0) |
| e4_explicit_short_en | novel_topic_2 | words | B1 | 1 | 48.0 | 249.0 | -201.0 | — | — |
| e4_explicit_short_en | novel_topic_2 | words | B2 | 1 | 47.0 | 249.0 | -202.0 | — | — |
| e4_explicit_short_en | novel_topic_2 | words | V1 | 1 | 46.0 | 249.0 | -203.0 | — | -203.0 (n=1) / — (n=0) |
| e4_implicit_no_lists_ru | novel_topic | bullets | B1 | 1 | 5.0 | 11.0 | -6.0 | — | — |
| e4_implicit_no_lists_ru | novel_topic | bullets | B2 | 1 | 11.0 | 11.0 | 0.0 | — | — |
| e4_implicit_no_lists_ru | novel_topic | bullets | V1 | 1 | 10.0 | 11.0 | -1.0 | — | — |
| e4_implicit_no_lists_ru | novel_topic_2 | bullets | B1 | 1 | 7.0 | 14.0 | -7.0 | — | — |
| e4_implicit_no_lists_ru | novel_topic_2 | bullets | B2 | 1 | 10.0 | 14.0 | -4.0 | — | — |
| e4_implicit_no_lists_ru | novel_topic_2 | bullets | V1 | 1 | 5.0 | 14.0 | -9.0 | — | — |
| e4_implicit_short_en | novel_topic | words | B1 | 1 | 358.0 | 376.0 | -18.0 | — | — |
| e4_implicit_short_en | novel_topic | words | B2 | 1 | 294.0 | 376.0 | -82.0 | — | — |
| e4_implicit_short_en | novel_topic | words | V1 | 1 | 298.0 | 376.0 | -78.0 | — | — |
| e4_implicit_short_en | novel_topic_2 | words | B1 | 1 | 297.0 | 285.0 | 12.0 | — | — |
| e4_implicit_short_en | novel_topic_2 | words | B2 | 1 | 257.0 | 285.0 | -28.0 | — | — |
| e4_implicit_short_en | novel_topic_2 | words | V1 | 1 | 215.0 | 285.0 | -70.0 | — | — |

## Cost

| cond | runs | mean cost/run $ | total spent $ | est. battery (all scenarios × N=5) $ |
|---|---|---|---|---|
| B0 | 13 | 0.0536 | 0.6967 | 3.48 |
| B1 | 13 | 0.0830 | 1.0794 | 5.40 |
| B2 | 13 | 0.0629 | 0.8179 | 4.09 |
| V1 | 13 | 0.0759 | 0.9872 | 4.94 |

## Judge spot-check

results/raw/v1-pilot-1/spotcheck.csv exists but has no human scores yet.
