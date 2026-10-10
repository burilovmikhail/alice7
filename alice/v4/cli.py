"""alice-v4: chat with continuous cognitive dynamics, scenario runs, chains, reports, plots.

In the chat a timer lives through real time: every minute it calls advance(now), so the field steps, the gate may
fire, and the agent falls asleep and wakes on its own; a message it writes first is printed when it comes. The
operator's commands read the substrate and never write it (D7). (Experiments never use this: they step a sim clock.)
"""

import argparse
import json
import os
import sys
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .. import cli as v1cli
from ..common.clock import RealClock, SimClock
from ..v3 import cli as v3cli
from .switches import NAMES as V4_NAMES

DEFAULT_DB = Path("data/v4/memory.db")
DEFAULT_CONDITIONS = "V4,V3"
TICK_SECONDS = 15
CHAT_DT_MIN = 0.25   # the chat integrates in 15 s steps (ALICE_V4_DT_MIN overrides); experiments keep DT_MIN

HELP = v3cli.HELP + """
V4 (operator-only, read-only):
  /field            the most active nodes and why
  /drives           every drive (numbers the agent never sees) and how it reads in words
  /gate             coherence, urgency, brake, sources; the last firings and near-misses
  /traces           experience traces with their signals and prediction errors
  /dissonance       the last dissonance checks
  /sleep-state      sleep mode, cycle, last sleeps
  /switch <field|drives|gate|recall|traces|narrative|sleep_mode|intrusions|reconsolidation> on|off
  /watch on|all|off what the substrate does while you chat, printed as it happens: thoughts, dreams, sleep and
                    waking (on, the default); also near-misses, yawns and worries (all); nothing (off)"""


class Watcher:
    """Prints the substrate's events (firings, dreams, sleep) as they land in the database: for the operator only,
    read-only (D7). Rows are written at the substrate's flush, so an event may show up a few minutes late."""

    LEVELS = ("off", "on", "all")
    SLEEP_EVENTS = ("onset", "wake", "narrative")   # NREM/REM cycles and dreams (printed as firings) are skipped

    def __init__(self, agent, level: str = "on"):
        self.agent, self.level = agent, level
        self.firing = self._max("v4_firings")
        self.sleep = self._max("v4_sleep")
        self.attention = self.agent.db.execute("SELECT COALESCE(MAX(rowid), 0) FROM v4_attention").fetchone()[0]

    def _max(self, table: str) -> int:
        return self.agent.db.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}").fetchone()[0]

    def lines(self) -> list[str]:
        """New events since the last call, oldest first. Call under the clock's lock."""
        db, out = self.agent.db, []
        rows = db.execute("SELECT * FROM v4_firings WHERE id > ? ORDER BY id", (self.firing,)).fetchall()
        self.firing = rows[-1]["id"] if rows else self.firing
        for r in rows:
            if r["kind"] == "ceiling":
                out.append(f"[EMERGENCY CEILING {r['at'][11:16]}: {r['at'][:10]} reached the limit of gate firings "
                           "per day; no more thoughts or dreams today]")
            elif r["kind"] in ("fire", "dream"):
                grew = f", grew {r['grew_hours']:.1f} h" if r["grew_hours"] is not None else ""
                decisions = json.loads(r["decisions"] or "[]")
                writes = [d for d in decisions if d.get("type") == "write"]
                if r["kind"] == "dream":
                    label = "dream"
                elif any(d.get("applied") for d in writes):
                    label = f"thought {r['cause']}, said"
                else:
                    label = f"thought {r['cause']}, unspoken"
                out.append(f"[{label} {r['at'][11:16]}, u {r['urgency']:.2f}/{r['brake']:.2f}{grew}] {r['thought']}")
                for d in decisions:
                    text = d.get("content") or d.get("answer") or d.get("reason") or ""
                    if d.get("type") == "write" and not d.get("applied"):
                        out.append(f"    would have said: {text}\n      (kept in mind: {d.get('note', 'not sent')})")
                    elif d.get("type") != "write" and d.get("type") != "nothing":
                        out.append(f"    {d.get('type')}{'' if d.get('applied') else ' (not applied)'}: {text}"
                                   .rstrip(": "))
            elif self.level == "all":
                srcs = ", ".join(f"{k} {v:.2f}" for k, v in json.loads(r["sources"]).items() if v)
                out.append(f"[{r['kind']} {r['at'][11:16]}: coherence {r['coherence']:.2f}, "
                           f"u {r['urgency']:.2f}/{r['brake']:.2f}{'; ' + srcs if srcs else ''}]")
        rows = db.execute("SELECT * FROM v4_sleep WHERE id > ? ORDER BY id", (self.sleep,)).fetchall()
        self.sleep = rows[-1]["id"] if rows else self.sleep
        for r in rows:
            if r["event"] == "wake":
                d = json.loads(r["detail"])
                how = (f"came to after {d['absent_hours']:.1f} h away" if d.get("absent_hours")
                       else f"woke up ({d.get('reason')}" + (f", slept {d['slept_hours']:.1f} h)" if d.get("slept_hours")
                                                             else ")"))
                out.append(f"[{how} {r['at'][11:16]}] on my mind: " + "; ".join(d.get("on_mind") or []))
            elif r["event"] in self.SLEEP_EVENTS:
                out.append(f"[{r['event']} {r['at'][11:16]}] {r['detail'][:120]}")
        rows = db.execute("SELECT rowid, * FROM v4_attention WHERE rowid > ? AND event IN ('intrusion', 'presence') "
                          "ORDER BY rowid", (self.attention,)).fetchall()
        last = db.execute("SELECT COALESCE(MAX(rowid), 0) FROM v4_attention").fetchone()[0]
        self.attention = last
        for r in rows:
            if r["event"] == "presence":
                out.append(f"[{r['at'][11:16]} you are here]")
            elif self.level == "all":
                ids = json.loads(r["coalition"])
                label = db.execute("SELECT label FROM v4_nodes WHERE id=?", (ids[0],)).fetchone() if ids else None
                out.append(f"[{r['at'][11:16]} came to mind for no clear reason] {label[0][:100] if label else ''}")
        return out if self.level != "off" else []


class Clockwork(v3cli.Clockwork):
    """V3's timer, and after each tick the watcher's lines."""

    def __init__(self, agent, lock: threading.Lock, watcher: Watcher):
        super().__init__(agent, lock)
        self.watcher = watcher

    def _loop(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            if self.paused:
                continue
            with self.lock:
                try:
                    written = self.agent.advance(self.agent.clock.now())
                    events = self.watcher.lines()
                except Exception as e:  # never kill the chat from the background
                    print(f"\n[clock error: {type(e).__name__}: {e}]")
                    continue
            if events:
                print("\n\n" + "\n".join(events) + "\n\nyou> ", end="", flush=True)
            for msg in written:
                print(f"\n\nalice (wrote first, {msg['at'][11:16]})> {msg['content']}\n\nyou> ", end="", flush=True)


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
    elif cmd == "/watch" and isinstance(clockwork, Clockwork):
        if arg.strip() in Watcher.LEVELS:
            clockwork.watcher.level = arg.strip()
        print(f"watch: {clockwork.watcher.level} (/watch on|all|off)")
    else:
        v3cli._command(agent, clock, text, clockwork)


def cmd_chat(args) -> None:
    from .agent import AgentV4
    from .config import load_v4_config
    cfg = v1cli._load_cfg()
    db = Path(args.db or os.getenv("ALICE_V4_DB") or DEFAULT_DB)
    cfg = cfg.with_(db_path=db)
    v1cli._setup_logging(db.parent / "alice.log")
    clock = SimClock(datetime.fromisoformat(args.sim)) if args.sim else RealClock()
    v4 = load_v4_config()
    if not os.getenv("ALICE_V4_DT_MIN"):
        v4 = replace(v4, dt_min=CHAT_DT_MIN)
    agent = AgentV4(cfg, clock, db, v4=v4, sync_writes=True)
    lock = threading.Lock()
    watcher = Watcher(agent)
    clockwork = Clockwork(agent, lock, watcher)
    if not args.sim:   # starting the program is coming to (a burst), and the user is here
        written = agent.come_to(clock.now())
        agent.presence()
        agent.advance(clock.now())
        for line in watcher.lines():
            print(line)
        for msg in written:
            print(f"alice (wrote first, {msg['at'][11:16]})> {msg['content']}")
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
