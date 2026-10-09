# V3 pass 1

Pass 1 (N = 1): V3 on E5 prose and short, E6 (2), E7 reminder, E8 (2), E9 (2), E10 duplicates = 10 scenarios;
V2 on the 5 new scenarios (E8–E10). V2 for unchanged scenarios comes from `results/v2-pass1` (V2 code unchanged).
2026-10-09. All 15 runs clean (no failed agent calls). Cost $8.20.

- Agent code: `ddb31a5`.
- Pilot runs before the pass (`results/archive/v3-smoke*`) led to the "Your own time" prompt section and to
  post-conversation wakes at night.
- After the pass, `f8e35d9` changed two rules (sleep and wakes no longer change lesson confidence; a quiet
  period before writing first, due intentions exempt from it and from the unanswered-message rule). E5 short and
  both E9 scenarios were rerun on that code: `report-fix.md` (cost $1.76). Raw data: `results/raw/v3-fix/`.

`report-pass1.md`, `report-fix.md`: the aggregated reports. Raw data (DBs, traces) lives in the gitignored
`results/raw/v3-pass1/` and `results/raw/v3-fix/`.
