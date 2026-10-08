"""Re-score saved replies with the current scenario definitions, without re-running any agent.

Measurement fixes (checks, rubrics, gold memories) then cost nothing or a few judge calls instead of a rerun.
A probe whose question or time changed can't be rescored: its saved reply answers a different situation.
"""

import json
import logging
import shutil
from pathlib import Path
from types import SimpleNamespace

from ..common.clock import RealClock, SimClock, parse_ts, wall_now
from ..common.config import Config
from ..common.db import connect
from ..common.llm import LLM, make_embedder
from ..common.trace import Tracer, export_jsonl
from ..v1.store import MemoryStore
from .runner import _DEFAULT, _write_json, apply_checks, apply_judge, git_info, summarize
from .scenario import load_scenario

log = logging.getLogger(__name__)

SCORED_FIELDS = ("checks", "passed", "gold", "judge")


def _gold_source(run_dir: Path, condition: str, probe_id: str, at: str, embed):
    """The probe fork's memory store (V1); None for conditions without one."""
    path = run_dir / "probes" / f"{probe_id}.db"
    if condition != "V1" or not path.exists():
        return None, None
    db = connect(path)
    return SimpleNamespace(store=MemoryStore(db, SimClock(parse_ts(at)), embed)), db


def rescore_run(run_dir: Path, cfg: Config, *, judge_llm: LLM | None = None, embed=_DEFAULT,
                use_judge: bool = True, rejudge: bool = False) -> dict:
    """Rescore one run directory in place (the original scores are kept once as scores.orig.json)."""
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "ok":
        return {"run": run_dir.name, "skipped": f"status {manifest.get('status')}"}
    if not Path(manifest.get("scenario_path") or "").exists():
        return {"run": run_dir.name, "skipped": f"scenario file not found: {manifest.get('scenario_path')}"}
    scenario = load_scenario(manifest["scenario_path"])
    probes = {p.id: p for p in scenario.probes}
    results = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))

    eval_db = connect(run_dir / "eval.db")
    tracer = Tracer(eval_db, RealClock())
    marks = tracer.marks()
    llm = (judge_llm or LLM(cfg)).bind(tracer)
    if embed is _DEFAULT:
        embed = make_embedder(cfg, llm)
    stats = {"run": run_dir.name, "probes": len(results), "changed": 0, "judge_calls": 0,
             "stale": [], "not_run": sorted(set(probes) - {r["probe"] for r in results})}
    try:
        for r in results:
            probe = probes.get(r["probe"])
            reason = ("probe removed from scenario" if probe is None
                      else "question changed since the run" if probe.ask != r["ask"]
                      else "probe time changed since the run" if r.get("offset") not in (None, str(probe.at))
                      else None)
            if reason:
                r["stale"] = reason
                stats["stale"].append(r["probe"])
                continue
            r.pop("stale", None)
            if "reply" not in r:
                continue
            before = json.dumps({k: r.get(k) for k in SCORED_FIELDS}, sort_keys=True, default=str)
            holder, db = _gold_source(run_dir, manifest["condition"], probe.id, r["at"], embed)
            try:
                apply_checks(r, probe, holder)
            finally:
                if db is not None:
                    db.close()
            r.update(measure=probe.measure, tags=probe.tags)
            if use_judge:
                stats["judge_calls"] += apply_judge(r, probe, llm, None if rejudge else r.get("judge"))
            if json.dumps({k: r.get(k) for k in SCORED_FIELDS}, sort_keys=True, default=str) != before:
                stats["changed"] += 1
        cost = tracer.totals(since=marks)
        export_jsonl(eval_db, run_dir / "traces", since=marks, extra={"timeline": "rescore"},
                     tables=("llm_calls",), append=True)
    finally:
        eval_db.close()

    if not (run_dir / "scores.orig.json").exists():
        shutil.copy(run_dir / "scores.json", run_dir / "scores.orig.json")
    totals = manifest.get("totals", {})
    totals["cost"] = round(totals.get("cost", 0) + cost["cost"], 6)
    totals["cost_judge"] = round(totals.get("cost_judge", 0) + cost["cost"], 6)
    manifest["totals"] = totals
    manifest.setdefault("rescores", []).append({
        "at": wall_now().isoformat(timespec="seconds"), "git": git_info(), "rejudge": rejudge,
        "judge_calls": stats["judge_calls"], "cost": cost["cost"], "changed": stats["changed"],
        "stale": stats["stale"]})
    _write_json(run_dir / "scores.json", results)
    _write_json(run_dir / "summary.json", summarize([r for r in results if "stale" not in r], totals))
    _write_json(run_dir / "manifest.json", manifest)
    stats["cost"] = cost["cost"]
    return stats


def rescore_all(root: Path, cfg: Config, **kwargs) -> list[dict]:
    return [rescore_run(m.parent, cfg, **kwargs) for m in sorted(Path(root).rglob("manifest.json"))]
