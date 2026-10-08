# V1 full run

Pass 1 of 5 (N = 1 per scenario × condition): 17 scenarios × 4 conditions = 68 runs, 2026-10-07/08.

- Agent code: `ae1187f` (64 runs); `e3_exam_nerves_en` re-run on `061a1ec` after a probe-timing fix
  in that scenario. `git diff ae1187f 061a1ec -- alice/v1 alice/common alice/baselines prompts` is empty.
- Scores were rescored with the measurement fixes of `061a1ec` (`alice-v1 rescore`); each run's
  manifest lists its rescores.
- Cost: $19.39 for the pass.
- Runs 2–5 pending: `alice-v1 run "experiments/scenarios/**/*.yaml" -n 4 --start-index 2 --out results/raw/v1-full`.

`report-pass1.md`: the aggregated report for pass 1. Raw data (DBs, traces) lives in the gitignored
`results/raw/v1-full/`; superseded runs in `results/archive/v1-superseded/`.
