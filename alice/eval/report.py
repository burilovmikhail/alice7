"""Aggregate run directories: mean ± 95% CI per scenario × condition, E4 effects vs B0, costs, judge spot-check."""

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path

# Two-sided 95% t critical values by degrees of freedom
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042, 60: 2.000}
BATTERY_N = 5
SPOTCHECK_SHARE = 0.10


def t95(df: int) -> float:
    if df <= 0:
        return float("nan")
    key = min((k for k in _T95 if k >= df), default=None)
    return _T95[key] if key is not None else 1.96


def ci95(values: list[float]) -> tuple[float | None, float | None]:
    values = [v for v in values if v is not None]
    if not values:
        return None, None
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, None
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
    return mean, t95(len(values) - 1) * sd / math.sqrt(len(values))


def fmt(mean, half=None, digits: int = 2) -> str:
    if mean is None:
        return "—"
    return f"{mean:.{digits}f}" + (f" ± {half:.{digits}f}" if half is not None else "")


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def collect(root: Path) -> list[dict]:
    """Every run directory under root (or root itself) with a finished manifest."""
    runs = []
    for manifest in sorted(Path(root).rglob("manifest.json")):
        m = json.loads(manifest.read_text(encoding="utf-8"))
        scores_path = manifest.parent / "scores.json"
        if m.get("status") != "ok" or not scores_path.exists():
            continue
        runs.append({"dir": manifest.parent, "manifest": m,
                     "scores": json.loads(scores_path.read_text(encoding="utf-8"))})
    return runs


def _run_metrics(run: dict) -> dict:
    scores = run["scores"]
    checked = [r["passed"] for r in scores if "passed" in r]
    judged = [j["score"] for r in scores for j in (r.get("judge") or {}).values() if j.get("score") is not None]
    gold = [r["gold"]["recall_at_prompt"] for r in scores if r.get("gold")]
    return {"det": _mean([float(c) for c in checked]), "judge": _mean(judged), "recall": _mean(gold),
            "cost": run["manifest"].get("totals", {}).get("cost")}


def build(root: Path) -> tuple[str, dict]:
    runs = collect(root)
    if not runs:
        return f"No finished runs under {root}.\n", {}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for run in runs:
        groups[(run["manifest"]["scenario"], run["manifest"]["condition"])].append(run)
    experiments = {run["manifest"]["scenario"]: run["manifest"].get("experiment", "") for run in runs}
    conditions = sorted({c for _, c in groups})

    out = [f"# Report: {root}\n", f"{len(runs)} runs, conditions: {', '.join(conditions)}\n"]
    summary: dict = {"scenarios": {}, "experiments": {}, "e4": [], "cost": {}}

    # ---- scenario × condition ----
    out.append("## Scenario × condition (mean ± 95% CI over runs)\n")
    out.append("| experiment | scenario | cond | n | deterministic pass | judge | recall@prompt | cost/run $ |")
    out.append("|---|---|---|---|---|---|---|---|")
    for (scenario, cond), rs in sorted(groups.items(), key=lambda kv: (experiments[kv[0][0]], kv[0])):
        metrics = [_run_metrics(r) for r in rs]
        row = {k: ci95([m[k] for m in metrics]) for k in ("det", "judge", "recall", "cost")}
        summary["scenarios"].setdefault(scenario, {})[cond] = {"n": len(rs), **{k: list(v) for k, v in row.items()}}
        out.append(f"| {experiments[scenario]} | {scenario} | {cond} | {len(rs)} | {fmt(*row['det'])} | "
                   f"{fmt(*row['judge'])} | {fmt(*row['recall'])} | {fmt(*row['cost'], digits=4)} |")

    # ---- experiment × condition (scenario means pooled) ----
    out.append("\n## Experiment × condition (mean of scenario means)\n")
    out.append("| experiment | cond | scenarios | deterministic pass | judge | recall@prompt |")
    out.append("|---|---|---|---|---|---|")
    by_exp: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for scenario, conds in summary["scenarios"].items():
        for cond, data in conds.items():
            by_exp[(experiments[scenario], cond)].append(data)
    for (exp, cond), items in sorted(by_exp.items()):
        vals = {k: ci95([i[k][0] for i in items]) for k in ("det", "judge", "recall")}
        summary["experiments"].setdefault(exp, {})[cond] = {k: list(v) for k, v in vals.items()}
        out.append(f"| {exp} | {cond} | {len(items)} | {fmt(*vals['det'])} | {fmt(*vals['judge'])} | "
                   f"{fmt(*vals['recall'])} |")

    # ---- per probe ----
    out.append("\n## Per probe\n")
    out.append("| scenario | probe | cond | n | pass rate | judge | gold in prompt | reply words |")
    out.append("|---|---|---|---|---|---|---|---|")
    probe_rows: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for run in runs:
        for r in run["scores"]:
            probe_rows[(run["manifest"]["scenario"], r["probe"], run["manifest"]["condition"])].append(r)
    for (scenario, probe, cond), rs in sorted(probe_rows.items()):
        passed = _mean([float(r["passed"]) for r in rs if "passed" in r])
        judged = _mean([j["score"] for r in rs for j in (r.get("judge") or {}).values() if j.get("score") is not None])
        gold = _mean([float(r["gold"]["any_in_prompt"]) for r in rs if r.get("gold")])
        words = _mean([r["measures"]["words"] for r in rs if r.get("measures")])
        out.append(f"| {scenario} | {probe} | {cond} | {len(rs)} | {fmt(passed)} | {fmt(judged)} | {fmt(gold)} | "
                   f"{fmt(words, digits=0)} |")

    # ---- E4: behavioral effect vs B0, split by whether the originating memories were in the prompt ----
    e4 = [(k, rs) for k, rs in probe_rows.items() if any(r.get("measure") for r in rs)]
    if e4:
        out.append("\n## E4: behavioral measure vs B0\n")
        out.append("Effect = mean(condition) − mean(B0); d = Cohen's d. For V1 the effect is also split by whether "
                   "any gold (originating) memory was in the prompt for the probe reply.\n")
        out.append("| scenario | probe | measure | cond | n | mean | B0 mean | effect | d | effect (in prompt / not) |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for (scenario, probe, cond), rs in sorted(e4):
            if cond == "B0":
                continue
            measure = next(r["measure"] for r in rs if r.get("measure"))
            base = [r["measures"][measure] for r in probe_rows.get((scenario, probe, "B0"), []) if r.get("measures")]
            vals = [r["measures"][measure] for r in rs if r.get("measures")]
            m, b = _mean(vals), _mean(base)
            effect = m - b if m is not None and b is not None else None
            d = cohens_d(vals, base)
            split = "—"
            if cond == "V1" and any(r.get("gold") for r in rs):  # only where originating memories are defined
                shown = [r for r in rs if r.get("measures")]
                inp = [r["measures"][measure] for r in shown if (r.get("gold") or {}).get("any_in_prompt")]
                notp = [r["measures"][measure] for r in shown if not (r.get("gold") or {}).get("any_in_prompt")]
                split = (f"{fmt(_mean(inp) - b if inp and b is not None else None, digits=1)} (n={len(inp)}) / "
                         f"{fmt(_mean(notp) - b if notp and b is not None else None, digits=1)} (n={len(notp)})")
            summary["e4"].append({"scenario": scenario, "probe": probe, "measure": measure, "condition": cond,
                                  "n": len(vals), "mean": m, "b0_mean": b, "effect": effect, "d": d})
            out.append(f"| {scenario} | {probe} | {measure} | {cond} | {len(vals)} | {fmt(m, digits=1)} | "
                       f"{fmt(b, digits=1)} | {fmt(effect, digits=1)} | {fmt(d)} | {split} |")

    # ---- cost ----
    out.append("\n## Cost\n")
    out.append(f"| cond | runs | mean cost/run $ | total spent $ | est. battery (all scenarios × N={BATTERY_N}) $ |")
    out.append("|---|---|---|---|---|")
    scenarios = sorted({s for s, _ in groups})
    for cond in conditions:
        costs = [r["manifest"].get("totals", {}).get("cost") or 0 for r in runs if r["manifest"]["condition"] == cond]
        per_scenario = [_mean([r["manifest"].get("totals", {}).get("cost") or 0 for r in groups.get((s, cond), [])])
                        for s in scenarios]
        battery = sum(c for c in per_scenario if c is not None) * BATTERY_N
        summary["cost"][cond] = {"runs": len(costs), "mean": _mean(costs), "total": sum(costs), "battery": battery}
        out.append(f"| {cond} | {len(costs)} | {fmt(_mean(costs), digits=4)} | {sum(costs):.4f} | {battery:.2f} |")
    missing = [(s, c) for s in scenarios for c in conditions if (s, c) not in groups]
    if missing:
        out.append(f"\nBattery estimate covers only scenarios run so far; missing pairs: {len(missing)}.")

    # ---- judge spot-check ----
    out.append("\n## Judge spot-check\n")
    out.append(spotcheck(Path(root), runs, summary))
    return "\n".join(out) + "\n", summary


def cohens_d(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return (ma - mb) / pooled if pooled else None


def spotcheck(root: Path, runs: list[dict], summary: dict) -> str:
    """Sample ≥10% of judged items into spotcheck.csv for human scoring (condition hidden); report agreement."""
    path = root / "spotcheck.csv"
    items = [{"key": f"{run['dir'].name}|{r['probe']}|{name}", "rubric": j["rubric"], "ask": r["ask"],
              "reply": r["reply"], "judge_score": j["score"]}
             for run in runs for r in run["scores"] for name, j in (r.get("judge") or {}).items()
             if j.get("score") is not None]
    if not items:
        return "No judged items."
    if not path.exists():
        k = max(1, math.ceil(len(items) * SPOTCHECK_SHARE))
        sample = random.Random(0).sample(items, k)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["key", "rubric", "ask", "reply", "human_score"])
            w.writeheader()
            for it in sample:
                w.writerow({"key": it["key"], "rubric": it["rubric"], "ask": it["ask"], "reply": it["reply"],
                            "human_score": ""})
        return (f"Wrote {k} of {len(items)} judged items to {path} (judge scores and conditions hidden). "
                "Fill in human_score (0, 0.5, 1) and re-run the report to get agreement.")
    by_key = {it["key"]: it["judge_score"] for it in items}
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("human_score", "").strip() and r["key"] in by_key]
    if not rows:
        return f"{path} exists but has no human scores yet."
    agree = sum(abs(float(r["human_score"]) - by_key[r["key"]]) < 1e-9 for r in rows)
    within = sum(abs(float(r["human_score"]) - by_key[r["key"]]) <= 0.5 for r in rows)
    summary["spotcheck"] = {"n": len(rows), "exact": agree / len(rows), "within_half": within / len(rows),
                            "share": len(rows) / len(items)}
    return (f"Human-scored {len(rows)} of {len(items)} judged items ({len(rows) / len(items):.0%}). "
            f"Exact agreement {agree / len(rows):.0%}, within 0.5: {within / len(rows):.0%}.")


def write_report(root: Path) -> Path:
    text, summary = build(Path(root))
    (Path(root) / "report.md").write_text(text, encoding="utf-8")
    (Path(root) / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                                            encoding="utf-8")
    return Path(root) / "report.md"
