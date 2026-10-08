"""Scenario runner: drives an agent along a simulated timeline, runs each probe on a fork, writes run artifacts."""

import json
import logging
import platform
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path

from ..baselines.agents import BASELINES
from ..baselines.b3 import ReflectiveCarryOverAgent
from ..common.clock import SimClock, iso, wall_now
from ..common.config import Config
from ..common.db import backup, connect
from ..common.llm import LLM
from ..common.text import content_stems, stem_overlap
from ..common.trace import Tracer, export_jsonl
from ..v1.agent import AgentV1
from ..v2.agent import AgentV2
from ..v2.config import load_v2_config
from .scenario import TURN_GAP, Probe, Scenario
from .scoring import check, judge, measures

log = logging.getLogger(__name__)

CONDITIONS = {"V1": AgentV1, "V2": AgentV2, **BASELINES, "B3": ReflectiveCarryOverAgent}
GOLD_COMMON_SHARE = 0.2  # stems in more than this share of memories are ignored when matching
GOLD_STEMS = 0.6    # share of a gold memory's stems a stored memory must contain to count as the same memory
# ...or embedding similarity, only for near-verbatim paraphrases. Calibrated on pilot data with bge-m3:
# true matches scored 0.58-0.94, unrelated facts about the same person up to 0.73, so similarity alone can't
# separate them; stems do the main work and this threshold stays above the observed non-matches.
GOLD_COSINE = 0.80

_DEFAULT = object()


def make_agent(condition: str, cfg: Config, clock, db_path: Path, *, llm: LLM | None = None, embed=_DEFAULT):
    cls = CONDITIONS[condition]
    kwargs = {"llm": llm, "sync_writes": True}
    if embed is not _DEFAULT:
        kwargs["embed"] = embed
    return cls(cfg, clock, db_path, **kwargs)


def git_info() -> dict:
    def run(*args) -> str | None:
        try:
            return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return None
    # Untracked files (notes, drafts) don't change what ran; only modified tracked files do
    return {"sha": run("rev-parse", "HEAD") or "uncommitted",
            "dirty": bool(run("status", "--porcelain", "--untracked-files=no"))}


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


class _ThreadFilter(logging.Filter):
    """With parallel runs (--jobs) every run's log handler sits on the root logger: keep only its own thread."""

    def __init__(self):
        super().__init__()
        self.thread = threading.get_ident()

    def filter(self, record: logging.LogRecord) -> bool:
        return record.thread == self.thread


def finished_runs(out_root: Path) -> set[tuple[str, str, int]]:
    """(scenario id, condition, run index) of every finished run under out_root, read from manifests,
    so --skip-existing doesn't depend on directory names or dates."""
    done = set()
    for path in Path(out_root).rglob("manifest.json"):
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if m.get("status") == "ok" and (path.parent / "scores.json").exists():
            done.add((m.get("scenario"), m.get("condition"), m.get("run")))
    return done


def timeline(transcript: list[dict]) -> list[dict]:
    """Mean behavioral measures of the agent's replies per session of the main timeline: learning curves
    without extra model calls."""
    sessions: dict[int, dict] = {}
    for t in transcript:
        s = sessions.setdefault(t["session"], {"session": t["session"], "filler": t.get("filler"), "at": t["at"],
                                               "replies": 0, "sums": {}})
        s["replies"] += 1
        for k, v in (t.get("measures") or measures(t["assistant"])).items():
            s["sums"][k] = s["sums"].get(k, 0) + v
    out = []
    for s in sorted(sessions.values(), key=lambda s: s["session"]):
        sums = s.pop("sums")
        out.append({**s, "mean": {k: round(v / s["replies"], 3) for k, v in sums.items()}})
    return out


def gold_status(agent, gold: list[str], context_ids: list[int]) -> dict | None:
    """Which gold memories exist in the store and whether they were in the prompt for this reply (V1 only).
    A stored memory matches a gold string by substring, by shared stems, or by embedding similarity."""
    store = getattr(agent, "store", None)
    if store is None or not gold:
        return None
    memories = store.all_memories()
    vec_ids, mat = store.vectors()
    # Stems found in a large share of memories (names) can't tell memories apart: don't count them
    df: dict[str, int] = {}
    for m in memories:
        for s in content_stems(m.content):
            df[s] = df.get(s, 0) + 1
    common = {s for s, n in df.items() if n > GOLD_COMMON_SHARE * len(memories)} if len(memories) >= 8 else set()
    items = []
    for g in gold:
        ids = {m.id for m in memories
               if g.lower() in m.content.lower() or stem_overlap(g, m.content, common) >= GOLD_STEMS}
        qv = store.embed_one(g)
        if qv is not None and vec_ids:
            ids |= {vec_ids[i] for i, sim in enumerate(mat @ qv) if sim >= GOLD_COSINE}
        ids = sorted(ids)
        items.append({"gold": g, "memory_ids": ids, "stored": bool(ids),
                      "in_prompt": any(i in context_ids for i in ids)})
    return {"items": items,
            "stored_rate": sum(i["stored"] for i in items) / len(items),
            "recall_at_prompt": sum(i["in_prompt"] for i in items) / len(items),
            "any_in_prompt": any(i["in_prompt"] for i in items)}


class Runner:
    def __init__(self, cfg: Config, out_root: Path, *, llm: LLM | None = None, judge_llm: LLM | None = None,
                 embed=_DEFAULT, use_judge: bool = True):
        self.cfg, self.out_root = cfg, Path(out_root)
        self.llm = llm or LLM(cfg)
        self.judge_llm = judge_llm or self.llm
        self.embed = embed
        self.use_judge = use_judge

    def run(self, scenario: Scenario, condition: str, run_index: int = 1) -> Path:
        stamp = wall_now()
        run_dir = self.out_root / f"{stamp:%Y-%m-%d}-{scenario.id}-{condition}-{run_index}"
        if run_dir.exists():
            run_dir = self.out_root / f"{stamp:%Y-%m-%d}-{scenario.id}-{condition}-{run_index}-{stamp:%H%M%S}"
        (run_dir / "probes").mkdir(parents=True)
        handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(_ThreadFilter())
        logging.getLogger().addHandler(handler)
        manifest = {
            "scenario": scenario.id, "scenario_path": str(scenario.path) if scenario.path else None,
            "experiment": scenario.experiment, "lang": scenario.lang, "condition": condition, "run": run_index,
            "started_at": stamp.isoformat(timespec="seconds"), "git": git_info(),
            "models": {"chat": self.cfg.chat_model, "fast": self.cfg.fast_model, "embed": self.cfg.embed_model,
                       "judge": self.cfg.judge_model if self.use_judge else None},
            "sampling": {"chat_temperature": self.cfg.chat_temperature, "seed": self.cfg.seed,
                         "provider_order": list(self.cfg.provider_order)},
            "config": self.cfg.public(), "python": sys.version.split()[0], "platform": platform.platform(),
            "status": "running",
        }
        _write_json(run_dir / "manifest.json", manifest)
        try:
            results, totals = self._run(scenario, condition, run_dir, manifest)
            manifest["status"] = "ok"
        except Exception as e:
            log.exception("run failed")
            manifest.update(status="error", error=f"{type(e).__name__}: {e}")
            _write_json(run_dir / "manifest.json", manifest)
            raise
        finally:
            logging.getLogger().removeHandler(handler)
            handler.close()
        manifest["finished_at"] = wall_now().isoformat(timespec="seconds")
        manifest["totals"] = totals
        _write_json(run_dir / "manifest.json", manifest)
        _write_json(run_dir / "scores.json", results)
        _write_json(run_dir / "summary.json", summarize(results, totals))
        return run_dir

    def _run(self, scenario: Scenario, condition: str, run_dir: Path, manifest: dict) -> tuple[list[dict], dict]:
        clock = SimClock(scenario.start)
        agent = make_agent(condition, self.cfg, clock, run_dir / "agent.db", llm=self.llm, embed=self.embed)
        if hasattr(agent, "describe"):  # version-specific settings (e.g. V2 models and switches)
            manifest["agent"] = agent.describe()
            _write_json(run_dir / "manifest.json", manifest)
        eval_db = connect(run_dir / "eval.db")
        judge_llm = self.judge_llm.bind(Tracer(eval_db, clock))
        traces = run_dir / "traces"
        transcript, results, probe_totals = [], [], []
        pending = list(scenario.probes)
        previous = None  # the agent's last reply on the main timeline: contingent turns react to it

        def run_due(before) -> None:
            while pending and (before is None or pending[0].at < before):
                probe = pending.pop(0)
                result, totals = self._probe(agent, condition, scenario, probe, clock, run_dir, judge_llm)
                results.append(result)
                probe_totals.extend(totals)

        try:
            for n, spec in enumerate(scenario.sessions, 1):
                run_due(spec.at)
                if spec.new_session:
                    agent.end_session()
                clock.set(max(clock.now(), scenario.start + spec.at))
                for turn in spec.turns:
                    if turn.wait:
                        clock.advance(turn.wait)
                    at = iso(clock.now())
                    user, branch = turn.choose(previous)
                    answer = agent.reply(user)
                    entry = {"session": n, "filler": spec.filler, "at": at, "user": user, "assistant": answer,
                             "context_ids": agent.last_context_ids(), "measures": measures(answer)}
                    if branch is not None:
                        entry["branch"] = branch
                    transcript.append(entry)
                    previous = answer
                    clock.advance(TURN_GAP)
            run_due(None)
            agent.end_session()  # final state includes the last episode
            main_totals = agent.cost()
            if hasattr(agent, "state_summary"):
                _write_json(run_dir / "state.json", agent.state_summary())
            export_jsonl(agent.db, traces, extra={"timeline": "main"}, append=True)
        finally:
            agent.close()
        export_jsonl(eval_db, traces, extra={"timeline": "judge"}, tables=("llm_calls",), append=True)
        judge_totals = Tracer(eval_db, clock).totals()
        eval_db.close()
        with open(run_dir / "transcript.jsonl", "w", encoding="utf-8") as f:
            for t in transcript:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        _write_json(run_dir / "timeline.json", timeline(transcript))
        return results, combine_totals(main=main_totals, probes=probe_totals, judge=judge_totals)

    def _probe(self, agent, condition: str, scenario: Scenario, probe: Probe, clock: SimClock, run_dir: Path,
               judge_llm: LLM) -> tuple[dict, dict]:
        """Run one probe on a fork of the current state so it never contaminates the main timeline.
        Returns the result and the cost records it caused (the shared session close, the first time)."""
        at = max(scenario.start + probe.at, clock.now())
        fork_path = run_dir / "probes" / f"{probe.id}.db"
        fork_clock = SimClock(at)
        extra_totals = []
        if probe.new_session:
            base, base_totals = self._closed_base(agent, condition, at, run_dir)
            if base_totals:
                extra_totals.append(base_totals)
            src = connect(base)
            try:
                backup(src, fork_path)
            finally:
                src.close()
            src = connect(fork_path)
            marks = Tracer(src, fork_clock).marks()  # the shared close is accounted for in the base
            src.close()
        else:
            marks = agent.tracer.marks()
            agent.snapshot(fork_path)
        fork = self._load_fork(condition, fork_path, fork_clock)
        result = {"probe": probe.id, "at": iso(at), "offset": str(probe.at), "ask": probe.ask,
                  "new_session": probe.new_session, "measure": probe.measure, "tags": probe.tags,
                  "kind": probe.kind, "pairs_with": probe.pairs_with, "fork_spec": probe.fork, "group": probe.group}
        try:
            if probe.fork:
                fork, result["fork"] = self._mutate(fork, condition, fork_path, fork_clock, probe.fork)
            reply = fork.reply(probe.ask)
            context_ids = fork.last_context_ids()
            result.update(reply=reply, context_ids=context_ids,
                          memory_block=getattr(fork, "last_memory_block", None))
            if hasattr(fork, "last_state"):
                result["v2_state"] = fork.last_state()
                chain = fork.explain()
                result["chain"] = {k: chain[k] for k in ("complete", "missing", "injected")}
            apply_checks(result, probe, fork)
            totals = fork.tracer.totals(since=marks)
            export_jsonl(fork.db, run_dir / "traces", since=marks, extra={"timeline": f"probe:{probe.id}"},
                         append=True)
        except Exception as e:
            log.exception("probe %s failed", probe.id)
            result["error"] = f"{type(e).__name__}: {e}"
            totals = fork.tracer.totals(since=marks)
        finally:
            fork.close()
        if self.use_judge:
            apply_judge(result, probe, judge_llm)
        return result, extra_totals + [totals]

    def _closed_base(self, agent, condition: str, at, run_dir: Path) -> tuple[Path, dict | None]:
        """The state at `at` after the open session has ended as it would have (episode; for V2 reflection and
        self-review). Made once per probe time and shared by every probe at that time, so probes that change the
        fork (E11-E13) and their controls start from the identical state, and the session close is paid once."""
        base = run_dir / "probes" / f"_base_{at:%Y%m%dT%H%M%S}.db"
        if base.exists():
            return base, None
        marks = agent.tracer.marks()  # before the snapshot: loading may already close a stale session (_recover)
        agent.snapshot(base)
        fork = self._load_fork(condition, base, SimClock(at))
        try:
            fork.end_session()
            totals = fork.tracer.totals(since=marks)
            export_jsonl(fork.db, run_dir / "traces", since=marks, extra={"timeline": f"probe-base:{iso(at)}"},
                         append=True)
        finally:
            fork.close()
        return base, totals


    def _load_fork(self, condition: str, path: Path, clock: SimClock, model: str | None = None):
        kwargs = {"sync_writes": True, "extract_after_reply": False,
                  **({} if self.embed is _DEFAULT else {"embed": self.embed})}
        cfg, llm = self.cfg, self.llm
        if model:  # E11: the agent's models change, its state doesn't; the fast model (periphery) stays (spec D12)
            cfg = self.cfg.with_(chat_model=model)
            llm = self.llm.bind(None)
            llm.cfg = cfg
            if condition == "V2":
                kwargs["v2"] = replace(load_v2_config(), reflect_model=model)
            elif condition == "B3":
                kwargs["notes_model"] = model
        return CONDITIONS[condition].load(path, cfg, clock, llm=llm, **kwargs)

    def _mutate(self, fork, condition: str, path: Path, clock: SimClock, spec: dict):
        """Apply a probe's fork changes. Conditions without the mechanism ignore a change and say so."""
        applied, ignored = {}, []
        if model := spec.get("model"):
            fork.close()  # the state after the session end is in the file; reopen it with the other models
            fork = self._load_fork(condition, path, clock, model)
            applied["model"] = model
        if switches := spec.get("switches"):
            if hasattr(fork, "apply_switches"):
                fork.apply_switches(switches)
                applied["switches"] = switches
            else:
                ignored.append("switches")
        if inject := spec.get("inject"):
            if hasattr(fork, "inject"):
                fork.inject(**inject)
                applied["inject"] = inject
            else:
                ignored.append("inject")
        return fork, {"applied": applied, "ignored": ignored}


def apply_checks(result: dict, probe: Probe, agent) -> None:
    """Deterministic scoring of a reply: behavioral measures, expectations, gold memories (`agent` needs `.store`
    for gold; anything else gives None). Shared by the runner and by rescoring of saved replies."""
    reply = result["reply"]
    result["measures"] = measures(reply)
    result.pop("checks", None)
    result.pop("passed", None)
    if probe.expect:
        checks = check(reply, probe.expect)
        result.update(checks=checks, passed=all(checks.values()))
    result["gold"] = gold_status(agent, probe.gold_memories, result.get("context_ids") or [])


def apply_judge(result: dict, probe: Probe, judge_llm: LLM, previous: dict | None = None) -> int:
    """LLM-judge every rubric of the probe. A rubric whose text is unchanged since `previous` keeps its score.
    Returns the number of judge calls made."""
    if "reply" not in result:
        return 0
    if not probe.judge:
        result.pop("judge", None)
        return 0
    calls, out = 0, {}
    for name, rubric in probe.judge.items():
        old = (previous or {}).get(name)
        if old and old.get("rubric") == rubric and old.get("score") is not None:
            out[name] = old
            continue
        calls += 1
        try:
            out[name] = {"rubric": rubric, **judge(judge_llm, rubric, probe.ask, result["reply"])}
        except Exception as e:
            log.exception("judge failed")
            out[name] = {"rubric": rubric, "score": None, "reason": f"error: {e}"}
    result["judge"] = out
    return calls


def combine_totals(*, main: dict, probes: list[dict], judge: dict) -> dict:
    parts = [main, *probes, judge]
    by: dict[str, dict] = {}
    for p in parts:
        for purpose, v in p.get("by_purpose", {}).items():
            acc = by.setdefault(purpose, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0,
                                          "errors": 0})
            for k in acc:
                acc[k] += v.get(k) or 0
    return {
        "cost": round(sum(p.get("cost", 0) for p in parts), 6),
        "prompt_tokens": sum(p.get("prompt_tokens", 0) for p in parts),
        "completion_tokens": sum(p.get("completion_tokens", 0) for p in parts),
        "calls": sum(p.get("calls", 0) for p in parts),
        "cost_main": main.get("cost", 0), "cost_probes": round(sum(p.get("cost", 0) for p in probes), 6),
        "cost_judge": judge.get("cost", 0), "by_purpose": by,
    }


def summarize(results: list[dict], totals: dict) -> dict:
    checked = [r for r in results if "passed" in r]
    judged = [j["score"] for r in results for j in (r.get("judge") or {}).values() if j.get("score") is not None]
    gold = [r["gold"]["recall_at_prompt"] for r in results if r.get("gold")]
    return {
        "probes": len(results), "errors": sum(1 for r in results if "error" in r),
        "deterministic_pass": sum(r["passed"] for r in checked) / len(checked) if checked else None,
        "judge_mean": sum(judged) / len(judged) if judged else None,
        "recall_at_prompt": sum(gold) / len(gold) if gold else None,
        "cost": totals["cost"], "tokens": totals["prompt_tokens"] + totals["completion_tokens"],
    }

