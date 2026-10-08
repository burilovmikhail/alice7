"""alice-v2: interactive chat with V2 inspection commands, scenario runs (V2 + references), chains, reports."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .. import cli as v1cli
from ..common.clock import RealClock, SimClock
from ..common.db import connect
from ..common.timefmt import ago
from .chain import explain, render
from .switches import NAMES

DEFAULT_DB = Path("data/v2/memory.db")
DEFAULT_CONDITIONS = "V2,V1,B0,B1,B2,B3"

HELP = v1cli.HELP + """
V2 (operator-only, never shown to the model):
  /lessons          active lessons (confidence, evidence); /lessons all — with retired
  /lesson <id>      a lesson's history and what caused each change
  /feedback         reactions not yet reflected on
  /reflect          run reflection now
  /portrait         current portrait and beliefs; /portrait history — every version
  /opinions         current opinions
  /intentions       open intentions; /intentions all
  /why [id]         the chain behind a reply (default: the last one)
  /switch <name> on|off   lessons, selfmodel, intentions (until the chat is restarted)"""


def _command(agent, clock, text: str) -> None:
    cmd, _, arg = text.partition(" ")
    arg = arg.strip()
    agent.drain()
    now = clock.now()
    if cmd == "/help":
        print(HELP)
    elif cmd == "/lessons":
        rows = agent.db.execute("SELECT * FROM lessons " + ("" if arg == "all" else "WHERE status='active' ")
                                + "ORDER BY status, confidence DESC").fetchall()
        for l in rows:
            print(f"#{l['id']} [{l['category']}, {l['status']}, {l['confidence']:.2f}, x{l['evidence']}] {l['rule']}"
                  + (f" | when {l['situation']}" if l["situation"] else ""))
        if not rows:
            print("no lessons yet")
    elif cmd == "/lesson":
        if not arg.lstrip("#").isdigit():
            print("usage: /lesson <id>")
            return
        for e in agent.lessons.history(int(arg.lstrip("#"))):
            print(f"{e['sim_ts']} {e['op']} -> {e['confidence']:.2f} feedback={e['feedback_ids']} "
                  f"message={e['message_id']}  {e['note']}")
    elif cmd == "/feedback":
        for f in agent.lessons.unreflected():
            print(f"#{f['id']} {f['kind']} ({f['signal']:+.1f}) {f['what']}" + (f" -> {f['hint']}" if f["hint"] else ""))
    elif cmd == "/reflect":
        print(f"{agent.reflector.reflect(session_summary=agent.session.summary if agent.session else '')} change(s)")
    elif cmd == "/portrait":
        rows = agent.db.execute("SELECT * FROM portraits ORDER BY id" + ("" if arg == "history" else " DESC LIMIT 1"))
        for p in rows.fetchall():
            print(f"#{p['id']} [{p['source']}, {ago(p['created_at'], now)}] {p['content']}")
            if p["changes"]:
                print(f"  changes: {p['changes']}")
            for b in agent.selfmodel.beliefs(p["id"]):
                print(f"  ({b['weight']:.1f}) {b['text']}" + (f"  <- #{b['parent_id']}" if b["parent_id"] else ""))
    elif cmd == "/opinions":
        for o in agent.selfmodel.opinions():
            print(f"#{o['id']} {o['topic']} ({o['stance']:+.1f}): {o['content']}")
    elif cmd == "/intentions":
        rows = agent.db.execute("SELECT * FROM intentions " + ("" if arg == "all" else "WHERE status='open' ")
                                + "ORDER BY id").fetchall()
        for i in rows:
            print(f"#{i['id']} [{i['status']}, {i['source']}, {ago(i['created_at'], now)}"
                  + (f", due {i['due_from']}" if i["due_from"] else "") + f"] {i['content']}")
    elif cmd == "/why":
        mid = int(arg.lstrip("#")) if arg.lstrip("#").isdigit() else agent.last_reply_id()
        print(render(agent.explain(mid)) if mid else "no replies yet")
    elif cmd == "/switch":
        name, _, value = arg.partition(" ")
        if name not in NAMES or value not in ("on", "off"):
            print(f"usage: /switch <{'|'.join(NAMES)}> on|off")
            return
        agent.apply_switches({name: value == "on"})
        print(f"switches: {agent.switches}")
    else:
        v1cli._command(agent, clock, text)


def cmd_chat(args) -> None:
    from .agent import AgentV2
    cfg = v1cli._load_cfg()
    # Not ALICE_DB: that is V1's database, and V2 would add its tables to it
    db = Path(args.db or os.getenv("ALICE_V2_DB") or DEFAULT_DB)
    cfg = cfg.with_(db_path=db)
    v1cli._setup_logging(db.parent / "alice.log")
    clock = SimClock(datetime.fromisoformat(args.sim)) if args.sim else RealClock()
    agent = AgentV2(cfg, clock, db, sync_writes=cfg.sync_writes)
    v1cli.chat_loop(agent, clock, f"alice-v2 [switches: {agent.switches}] — db: {agent.db_path}. "
                                  "/help for commands, /quit to exit.", _command)


def cmd_chain(args) -> None:
    """The chain behind a reply in a saved run: the main timeline, or a probe's fork with --probe."""
    run_dir = Path(args.run_dir)
    path = run_dir / "probes" / f"{args.probe}.db" if args.probe else run_dir / "agent.db"
    if not path.exists():
        sys.exit(f"no database at {path}")
    db = connect(path)
    try:
        mid = args.message_id
        if mid is None:  # the probe's reply, or the last reply of the run
            row = db.execute("SELECT MAX(message_id) FROM turn_state").fetchone()
            mid = row[0] if row else None
        if mid is None:
            sys.exit("no V2 replies in this database")
        chain = explain(db, mid)
        print(json.dumps(chain, ensure_ascii=False, indent=2, default=str) if args.json else render(chain))
    finally:
        db.close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="alice-v2", description="V2: adaptive identity")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("chat", help="interactive chat with the V2 agent")
    p.add_argument("--db", help=f"SQLite file (default: ALICE_V2_DB if set, else {DEFAULT_DB})")
    p.add_argument("--sim", metavar="START", help="use a simulated clock starting at START (ISO), enables /advance")
    p.set_defaults(func=cmd_chat)

    p = sub.add_parser("run", help="run scenario(s) under a simulated clock")
    p.add_argument("scenarios", nargs="+", help="scenario YAML files or globs")
    p.add_argument("--conditions", default=DEFAULT_CONDITIONS)
    p.add_argument("-n", type=int, default=1, help="runs per scenario × condition")
    p.add_argument("--out", default="results/raw")
    p.add_argument("--no-judge", action="store_true", help="deterministic checks only")
    p.add_argument("--estimate", action="store_true", help="print a cost estimate and exit")
    p.add_argument("--start-index", type=int, default=1, help="number of the first run")
    p.add_argument("--jobs", type=int, default=1, help="runs in parallel")
    p.add_argument("--skip-existing", action="store_true", help="skip runs already finished under --out")
    p.set_defaults(func=v1cli.cmd_run)

    p = sub.add_parser("chain", help="the causal chain behind a V2 reply in a saved run (E7)")
    p.add_argument("run_dir")
    p.add_argument("message_id", nargs="?", type=int, help="default: the probe's reply / the last reply")
    p.add_argument("--probe", help="look in this probe's fork instead of the main timeline")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_chain)

    p = sub.add_parser("rescore", help="re-score saved replies with current scenario checks/rubrics")
    p.add_argument("run_dir")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--rejudge", action="store_true")
    p.set_defaults(func=v1cli.cmd_rescore)

    p = sub.add_parser("report", help="aggregate scores from run directories")
    p.add_argument("run_dir")
    p.set_defaults(func=v1cli.cmd_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
