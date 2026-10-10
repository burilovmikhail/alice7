"""alice-v4: chat with continuous cognitive dynamics, scenario runs, chains, reports, plots.

In the chat a timer lives through real time: every minute it calls advance(now), so the field steps, the gate may
fire, and the agent falls asleep and wakes on its own; a message it writes first is printed when it comes. The
operator's commands read the substrate and never write it (D7). (Experiments never use this: they step a sim clock.)
"""

import argparse
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from .. import cli as v1cli
from ..common.clock import RealClock, SimClock
from ..v3 import cli as v3cli
from .switches import NAMES as V4_NAMES

DEFAULT_DB = Path("data/v4/memory.db")
DEFAULT_CONDITIONS = "V4,V3"

HELP = v3cli.HELP + """
V4 (operator-only, read-only):
  /field            the most active nodes and why
  /drives           every drive (numbers the agent never sees) and how it reads in words
  /gate             coherence, urgency, brake, sources; the last firings and near-misses
  /traces           experience traces with their signals and prediction errors
  /dissonance       the last dissonance checks
  /sleep-state      sleep mode, cycle, last sleeps
  /switch <field|drives|gate|recall|traces|narrative|sleep_mode|intrusions|reconsolidation> on|off"""


def _command(agent, clock, text: str, clockwork=None) -> None:
    from .fieldlog import gate_state, top_nodes
    cmd, _, arg = text.partition(" ")
    a = agent._agent if isinstance(agent, v3cli.Locked) else agent
    a.drain()
    db = a.db
    if cmd == "/help":
        print(HELP)
    elif cmd in ("/field", "/drives", "/gate", "/sleep-state") and not a.field_on:
        print("the field is off")
    elif cmd == "/field":
        print("\n".join(top_nodes(a)))
    elif cmd == "/drives":
        s = a.substrate
        print(", ".join(f"{k} {v:.2f}" for k, v in s.drives.x.items()))
        print("in words: " + s.drives.words(a._silence_seconds()))
    elif cmd == "/gate":
        print("\n".join(gate_state(a)))
    elif cmd == "/traces":
        for r in db.execute("SELECT * FROM v4_traces ORDER BY id DESC LIMIT 10").fetchall():
            print(f"#{r['id']} {r['created_at'][5:16]} {r['kind']} signal {r['signal']:+.2f} expected "
                  f"{r['expected']:+.2f} PE {r['pe']:+.2f}: {r['situation'][:60]!r} -> {r['reaction'][:60]!r}")
    elif cmd == "/dissonance":
        for r in db.execute("SELECT * FROM v4_dissonance ORDER BY id DESC LIMIT 10").fetchall():
            print(f"{r['at'][5:16]} ({r['weight']:.1f}) {r['belief'][:70]}: contradicting {r['share']:.0%} -> "
                  f"{r['value']:.2f}")
    elif cmd == "/sleep-state":
        sl = a.substrate.sleep
        print(f"mode {sl.mode}, cycle {sl.cycle}, dreams tonight {sl.dreams}, S {a.substrate.drives.get('S'):.2f}")
        for r in db.execute("SELECT * FROM v4_sleep ORDER BY id DESC LIMIT 10").fetchall():
            print(f"  {r['at'][5:16]} {r['event']:10} {r['detail'][:90]}")
    elif cmd == "/switch" and arg.strip().split(" ")[0] in V4_NAMES:
        name, _, value = arg.strip().partition(" ")
        if value not in ("on", "off"):
            print(f"usage: /switch {name} on|off")
            return
        a.apply_switches({name: value == "on"})
        print(f"V4 switches: {a.v4_switches}")
    else:
        v3cli._command(agent, clock, text, clockwork)


def cmd_chat(args) -> None:
    from .agent import AgentV4
    cfg = v1cli._load_cfg()
    db = Path(args.db or os.getenv("ALICE_V4_DB") or DEFAULT_DB)
    cfg = cfg.with_(db_path=db)
    v1cli._setup_logging(db.parent / "alice.log")
    clock = SimClock(datetime.fromisoformat(args.sim)) if args.sim else RealClock()
    agent = AgentV4(cfg, clock, db, sync_writes=True)
    lock = threading.Lock()
    clockwork = v3cli.Clockwork(agent, lock)
    if not args.sim:
        clockwork.start()
    locked = v3cli.Locked(agent, lock)
    try:
        v1cli.chat_loop(locked, clock, f"alice-v4 [V2: {agent.switches}; V3: {agent.v3_switches}; "
                                       f"V4: {agent.v4_switches}] — db: {db}. /help for commands, /quit to exit.",
                        lambda ag, ck, text: _command(ag, ck, text, clockwork))
    finally:
        clockwork.stop()
        agent.close()


def cmd_plot(args) -> None:
    from .plot import plot
    target = Path(args.target)
    path = target / "agent.db" if target.is_dir() else target
    if target.is_dir() and args.probe:
        path = target / "probes" / f"{args.probe}.db"
    if not path.exists():
        sys.exit(f"no database at {path}")
    out = Path(args.out) if args.out else path.with_suffix(".png")
    nodes = [int(n) for n in args.nodes.split(",")] if args.nodes else None
    print(plot(path, out, start=args.start, end=args.end, nodes=nodes))


def cmd_pilot(args) -> None:
    from .pilot import run_p0
    print(run_p0(v1cli._load_cfg(), Path(args.out)))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="alice-v4", description="V4: continuous cognitive dynamics")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("chat", help="interactive chat; a timer lives through real time while you are away")
    p.add_argument("--db", help=f"SQLite file (default: ALICE_V4_DB if set, else {DEFAULT_DB})")
    p.add_argument("--sim", metavar="START", help="simulated clock (no timer; /advance moves it)")
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("run", help="run scenario(s) under a simulated clock")
    p.add_argument("scenarios", nargs="+")
    p.add_argument("--conditions", default=DEFAULT_CONDITIONS)
    p.add_argument("-n", type=int, default=1)
    p.add_argument("--out", default="results/raw")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--estimate", action="store_true")
    p.add_argument("--start-index", type=int, default=1)
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--skip-existing", action="store_true")
    p.set_defaults(func=v1cli.cmd_run)

    p = sub.add_parser("chain", help="the causal chain behind a reply in a saved run")
    p.add_argument("run_dir")
    p.add_argument("message_id", nargs="?", type=int)
    p.add_argument("--probe")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=v3cli.cmd_chain)

    p = sub.add_parser("rescore", help="re-score saved replies")
    p.add_argument("run_dir")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--rejudge", action="store_true")
    p.set_defaults(func=v1cli.cmd_rescore)

    p = sub.add_parser("report", help="aggregate scores from run directories")
    p.add_argument("run_dir")
    p.set_defaults(func=v1cli.cmd_report)

    p = sub.add_parser("plot", help="drives, activations, coherence and urgency, sleep stages, as a PNG")
    p.add_argument("target", help="a run directory (its agent.db), or a database file (a probe fork)")
    p.add_argument("--probe", help="with a run directory: the probe fork to plot")
    p.add_argument("--from", dest="start", help="ISO time")
    p.add_argument("--to", dest="end", help="ISO time")
    p.add_argument("--nodes", help="comma-separated node ids to draw in color")
    p.add_argument("--out", help="PNG path (default: next to the database)")
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("pilot", help="P0: three nodes, one collision (six replies, cents)")
    p.add_argument("name", choices=["p0"])
    p.add_argument("--out", default="results/v4-pilots/p0")
    p.set_defaults(func=cmd_pilot)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
