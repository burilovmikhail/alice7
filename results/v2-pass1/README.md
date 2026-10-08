# V2 pass 1

Pass 1 (N = 1 per scenario × condition): E5–E7, 9 scenarios × 6 conditions (V2, V1, B0, B1, B2, B3) = 54 runs,
2026-10-08.

- Agent code: `bde557a`. Manifests of runs started after `613a471` record that revision; the difference is
  harness-only (`git diff bde557a 613a471 -- alice/v1 alice/v2 alice/common alice/baselines prompts` is empty).
- Network failures: 7 runs failed and 3 finished with failed agent model calls (degraded). All 10 were re-run
  (`run --skip-existing`); degraded originals stay on disk and are left out of the report. Judge failures were
  filled in by `rescore`.
- Cost: $32.74 recorded for finished runs, plus unrecorded spend of the failed attempts.
- Not run: E1–E4 for V2 and B3 (memory regression check); runs 2–5.
- Pilot runs before this pass (prompt fixes after each) are in the gitignored `results/archive/v2-smoke*`.

`report-pass1.md`: the aggregated report for this pass. Raw data (DBs, traces) lives in the gitignored
`results/raw/v2-pass1/`.
