"""alice-v1: interactive chat, scenario runs, reports."""

import argparse
import glob
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .common.clock import RealClock, SimClock, parse_offset
from .common.config import ConfigError, load_config
from .common.timefmt import ago

HELP = """Operator commands (never shown to the model):
  /end              finish the session (it becomes an episode)
  /debug            toggle printing the <memory> block
  /memory [query]   search memory (no query: everything active)
  /core             core facts
  /episodes         episodes
  /thread <id>      what a memory grew out of (cause chain)
  /forget <id>      forget a memory (closed, not deleted)
  /cost             tokens and cost so far
  /time             current (sim) time
  /advance 2d       move the sim clock (only with --sim)
  /quit             exit"""


def _setup_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, filename=path, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "openai", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _load_cfg():
    try:
        return load_config()
    except ConfigError as e:
        sys.exit(f"error: {e}")


# ---------- chat ----------

def cmd_chat(args) -> None:
    cfg = _load_cfg()
    if args.db:
        cfg = cfg.with_(db_path=Path(args.db))
    _setup_logging(cfg.db_path.parent / "alice.log")
    clock = SimClock(datetime.fromisoformat(args.sim)) if args.sim else RealClock()
    if args.agent == "V1":
        from .v1.agent import AgentV1
        agent = AgentV1(cfg, clock, cfg.db_path, sync_writes=cfg.sync_writes)
    else:
        from .baselines.agents import BASELINES
        agent = BASELINES[args.agent](cfg, clock, cfg.db_path.with_name(f"{args.agent.lower()}.db"))
    debug = False
    print(f"alice-v1 [{agent.name}] — db: {agent.db_path}. /help for commands, /quit to exit.")
    try:
        while True:
            try:
                text = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            if text.startswith("/"):
                if text in ("/quit", "/exit", "/q"):
                    break
                if text == "/debug":
                    debug = not debug
                    print(f"debug {'on' if debug else 'off'}")
                    continue
                _command(agent, clock, text)
                continue
            try:
                answer = agent.reply(text)
            except Exception as e:
                logging.exception("reply failed")
                print(f"[error: {type(e).__name__}: {e}]")
                continue
            if debug and getattr(agent, "last_memory_block", None):
                print("\n--- <memory> ---\n" + agent.last_memory_block + "\n--- </memory> ---")
            print(f"\nalice> {answer}")
    finally:
        agent.close()  # drains pending writes; an open session resumes (or is finalized) next start


def _command(agent, clock, text: str) -> None:
    cmd, _, arg = text.partition(" ")
    arg = arg.strip()
    agent.drain()
    store = getattr(agent, "store", None)
    now = clock.now()
    if cmd == "/help":
        print(HELP)
    elif cmd == "/end":
        agent.end_session()
        print("session finished")
    elif cmd == "/cost":
        t = agent.cost()
        print(f"{t['calls']} calls, {t['prompt_tokens']:,} prompt + {t['completion_tokens']:,} completion tokens, "
              f"${t['cost']:.4f}")
        for purpose, v in sorted(t["by_purpose"].items()):
            print(f"  {purpose:10} {v['calls']:4} calls  ${v['cost']:.4f}")
    elif cmd == "/time":
        print(f"{now:%Y-%m-%d %H:%M} ({'sim' if isinstance(clock, SimClock) else 'real'} clock)")
    elif cmd == "/advance":
        if not isinstance(clock, SimClock):
            print("only with --sim")
            return
        try:
            clock.advance(parse_offset(arg or "1d"))
        except ValueError as e:
            print(e)
            return
        print(f"now {clock.now():%Y-%m-%d %H:%M}")
    elif store is None:
        print("memory commands are V1-only")
    elif cmd == "/memory":
        if arg:
            from .common.timeparse import parse_time_range
            from .v1.retrieval import search
            result = search(store, arg, now=now, date_range=parse_time_range(arg, now.date()), include_core=True)
            for h in result.hits:
                ch = ", ".join(f"{k}={v:.2f}" for k, v in h.channels.items())
                print(f"#{h.memory.id} [{h.memory.kind}/{h.memory.tier}] score={h.score:.2f} alive={h.alive:.2f} "
                      f"({ch})\n    {h.memory.content}")
            if not result.hits:
                print("nothing found")
        else:
            for m in store.all_memories():
                print(f"#{m.id} [{m.kind}/{m.tier}, {ago(m.valid_from, now)}] {m.content}")
    elif cmd == "/core":
        for m in store.core_memories():
            print(f"#{m.id} {m.content}")
    elif cmd == "/episodes":
        for m in store.recent_episodes(50):
            print(f"#{m.id} [{ago(m.valid_from, now)}] {m.content}")
    elif cmd in ("/thread", "/forget"):
        if not arg.lstrip("#").isdigit():
            print(f"usage: {cmd} <id>")
            return
        mid = int(arg.lstrip("#"))
        if cmd == "/forget":
            print("forgotten" if store.forget(mid) else "no such active memory")
            return
        m = store.memories_by_ids([mid], active_only=False).get(mid)
        if not m:
            print("no such memory")
            return
        print(f"#{m.id} {m.content}")
        for c in store.causes(mid, depth=5):
            print(f"  ↳ grew out of #{c.id} ({ago(c.valid_from, now)}): {c.content}")
    else:
        print(f"unknown command {cmd}; /help")


# ---------- run / report ----------

def _expand(patterns: list[str]) -> list[Path]:
    paths = []
    for p in patterns:
        matched = sorted(glob.glob(p, recursive=True)) or [p]
        paths.extend(Path(m) for m in matched)
    return paths


def cmd_run(args) -> None:
    from .eval.runner import CONDITIONS, Runner
    from .eval.scenario import load_scenario

    conditions = [c.strip().upper() for c in args.conditions.split(",") if c.strip()]
    if unknown := [c for c in conditions if c not in CONDITIONS]:
        sys.exit(f"unknown condition(s): {', '.join(unknown)}; choose from {', '.join(CONDITIONS)}")
    scenarios = [load_scenario(p) for p in _expand(args.scenarios)]
    if args.estimate:
        from .eval.estimate import estimate
        cfg = load_config(require_key=False)
        print(estimate(scenarios, conditions, cfg, args.n, judge=not args.no_judge))
        return
    cfg = _load_cfg()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)
    for noisy in ("httpx", "openai", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    runner = Runner(cfg, out, use_judge=not args.no_judge)
    failures = 0
    for sc in scenarios:
        for cond in conditions:
            for i in range(1, args.n + 1):
                print(f"== {sc.id} / {cond} / run {i}", flush=True)
                try:
                    run_dir = runner.run(sc, cond, i)
                except Exception as e:
                    failures += 1
                    print(f"   FAILED: {type(e).__name__}: {e}", flush=True)
                    continue
                s = json.loads((run_dir / "summary.json").read_text())
                print(f"   -> {run_dir}  pass={s['deterministic_pass']} judge={s['judge_mean']} "
                      f"recall={s['recall_at_prompt']} cost=${s['cost']:.4f}", flush=True)
    if failures:
        sys.exit(f"{failures} run(s) failed")


def cmd_report(args) -> None:
    from .eval.report import write_report
    path = write_report(Path(args.run_dir))
    print(path.read_text(encoding="utf-8"))
    print(f"(written to {path})")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="alice-v1", description="V1: LLM chat with persistent memory")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("chat", help="interactive chat")
    p.add_argument("--db", help="SQLite file (default: ALICE_DB)")
    p.add_argument("--sim", metavar="START", help="use a simulated clock starting at START (ISO), enables /advance")
    p.add_argument("--agent", default="V1", choices=["V1", "B0", "B1", "B2"], help="chat with a baseline instead")
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("run", help="run scenario(s) under a simulated clock")
    p.add_argument("scenarios", nargs="+", help="scenario YAML files or globs")
    p.add_argument("--conditions", default="V1,B0,B1,B2")
    p.add_argument("-n", type=int, default=1, help="runs per scenario × condition")
    p.add_argument("--out", default="results/raw")
    p.add_argument("--no-judge", action="store_true", help="deterministic checks only")
    p.add_argument("--estimate", action="store_true", help="print a cost estimate and exit")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="aggregate scores from run directories")
    p.add_argument("run_dir", help="a run directory or a directory containing runs")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
