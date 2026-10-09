"""alice-v3: chat with continuous cognition, scenario runs, chains, reports.

In the chat a timer lives through real time: every minute it calls advance(now), so the stream ticks, wakes and
sleep happen while you are away, and a message the agent writes first is printed when it comes. A lock keeps the
timer and your turns from touching the database at once. (Experiments never use this: they step a sim clock.)
"""

import argparse
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from .. import cli as v1cli
from ..common.clock import RealClock, SimClock
from ..common.timefmt import ago
from ..v2 import cli as v2cli
from .affect import words
from .switches import NAMES as V3_NAMES

DEFAULT_DB = Path("data/v3/memory.db")
DEFAULT_CONDITIONS = "V3,V2"
TICK_SECONDS = 60

HELP = v2cli.HELP + """
V3 (operator-only):
  /stream           recent background thoughts
  /pressure         the last checks of the monitor (numbers the agent never sees)
  /wakes            recent wakes and what they decided
  /mood             mood and the moment
  /outbox           messages the agent wrote first
  /schedule         the last scheduled events
  /thoughts         the agent's own thoughts and open questions
  /hibernate        stop / resume the clock
  /switch <stream|wakes|sleep|affect|initiative|later> on|off"""


class Clockwork:
    """The timer: advance(now) every TICK_SECONDS, under the same lock as the user's turns."""

    def __init__(self, agent, lock: threading.Lock):
        self.agent, self.lock = agent, lock
        self.paused = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="v3-clock", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            if self.paused:
                continue
            with self.lock:
                try:
                    written = self.agent.advance(self.agent.clock.now())
                except Exception as e:  # never kill the chat from the background
                    print(f"\n[clock error: {type(e).__name__}: {e}]")
                    continue
            for msg in written:
                print(f"\n\nalice (wrote first, {msg['at'][11:16]})> {msg['content']}\n\nyou> ", end="", flush=True)


class Locked:
    """The agent as the chat loop sees it: replies and commands under the clock's lock; silence caught up first."""

    def __init__(self, agent, lock: threading.Lock):
        self._agent, self._lock = agent, lock

    def __getattr__(self, name):
        return getattr(self._agent, name)

    def reply(self, text: str) -> str:
        with self._lock:
            for msg in self._agent.advance(self._agent.clock.now()):
                print(f"\nalice (wrote first, {msg['at'][11:16]})> {msg['content']}")
            return self._agent.reply(text)


def _command(agent, clock, text: str, clockwork: Clockwork | None = None) -> None:
    cmd, _, arg = text.partition(" ")
    arg = arg.strip()
    a = agent._agent if isinstance(agent, Locked) else agent
    a.drain()
    now = clock.now()
    db = a.db
    if cmd == "/help":
        print(HELP)
    elif cmd == "/stream":
        for r in reversed(db.execute("SELECT * FROM stream_thoughts ORDER BY id DESC LIMIT 12").fetchall()):
            print(f"[{r['mode']}, {ago(r['at'], now)}, novelty {r['novelty']:.2f}] {r['content']}")
    elif cmd == "/pressure":
        for r in reversed(db.execute("SELECT * FROM pressure_log ORDER BY id DESC LIMIT 10").fetchall()):
            print(f"{r['at'][5:16]} {r['value']:.2f} / {r['threshold']:.2f}{' WOKE' if r['woke'] else ''}  "
                  f"{r['parts']}")
    elif cmd == "/wakes":
        for r in reversed(db.execute("SELECT * FROM wakes ORDER BY id DESC LIMIT 8").fetchall()):
            print(f"#{r['id']} {r['at'][5:16]} {'productive' if r['productive'] else 'empty'}: {r['thought']}")
            for d in json.loads(r["decisions"] or "[]"):
                print(f"    {d.get('type')}{'' if d.get('applied') else ' (not applied)'}: "
                      f"{d.get('content') or d.get('rule') or d.get('answer') or ''}")
    elif cmd == "/mood":
        print(f"mood: {words(a.affect.mood(now))}; now: {words(a.affect.current(now))}")
    elif cmd == "/outbox":
        for r in db.execute("SELECT * FROM outbox ORDER BY message_id").fetchall():
            print(f"{r['at'][5:16]} {r['content']}")
    elif cmd == "/schedule":
        for r in reversed(db.execute("SELECT * FROM schedule_log ORDER BY id DESC LIMIT 15").fetchall()):
            print(f"{r['at'][5:16]} {r['event']:14} {'ran' if r['ran'] else 'skipped'} {r['note'][:80]}")
    elif cmd == "/thoughts":
        for r in db.execute("SELECT * FROM thoughts ORDER BY id DESC LIMIT 10").fetchall():
            print(f"[{r['source']}, {ago(r['at'], now)}] {r['content']}")
        for q in a.thoughts.open_questions():
            print(f"? {q['content']}")
    elif cmd == "/hibernate" and clockwork is not None:
        clockwork.paused = not clockwork.paused
        print("clock stopped" if clockwork.paused else "clock running")
    elif cmd == "/switch" and arg.split(" ")[0] in V3_NAMES:
        name, _, value = arg.partition(" ")
        if value not in ("on", "off"):
            print(f"usage: /switch {name} on|off")
            return
        a.apply_switches({name: value == "on"})
        print(f"V3 switches: {a.v3_switches}")
    else:
        v2cli._command(a, clock, text)


def cmd_chat(args) -> None:
    from .agent import AgentV3
    cfg = v1cli._load_cfg()
    db = Path(args.db or os.getenv("ALICE_V3_DB") or DEFAULT_DB)
    cfg = cfg.with_(db_path=db)
    v1cli._setup_logging(db.parent / "alice.log")
    clock = SimClock(datetime.fromisoformat(args.sim)) if args.sim else RealClock()
    agent = AgentV3(cfg, clock, db, sync_writes=True)   # one lock instead of a background writer
    lock = threading.Lock()
    clockwork = Clockwork(agent, lock)
    if not args.sim:
        clockwork.start()
    locked = Locked(agent, lock)
    try:
        v1cli.chat_loop(locked, clock, f"alice-v3 [V2: {agent.switches}; V3: {agent.v3_switches}] — db: {db}. "
                                       "/help for commands, /quit to exit.",
                        lambda ag, ck, text: _command(ag, ck, text, clockwork))
    finally:
        clockwork.stop()


def cmd_chain(args) -> None:
    """As alice-v2 chain, with wake- and sleep-caused lesson changes counted as grounded."""
    import sys
    from ..common.db import connect
    from ..v2.chain import explain, render
    from .agent import ground_v3_causes
    path = Path(args.run_dir) / "probes" / f"{args.probe}.db" if args.probe else Path(args.run_dir) / "agent.db"
    if not path.exists():
        sys.exit(f"no database at {path}")
    db = connect(path)
    try:
        mid = args.message_id or db.execute("SELECT MAX(message_id) FROM turn_state").fetchone()[0]
        if mid is None:
            sys.exit("no V2/V3 replies in this database")
        chain = ground_v3_causes(explain(db, mid), db)
        print(json.dumps(chain, ensure_ascii=False, indent=2, default=str) if args.json else render(chain))
    finally:
        db.close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="alice-v3", description="V3: continuous cognition")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("chat", help="interactive chat; a timer lives through real time while you are away")
    p.add_argument("--db", help=f"SQLite file (default: ALICE_V3_DB if set, else {DEFAULT_DB})")
    p.add_argument("--sim", metavar="START", help="simulated clock (no timer; /advance moves it, silence is "
                                                  "lived through at the next message)")
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
    p.set_defaults(func=cmd_chain)

    p = sub.add_parser("rescore", help="re-score saved replies")
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
