"""alice-v4 web: the chat and a live view of the substrate in a browser (operator-only, read-only for the agent: D7).

A local HTTP server (standard library only) on one agent: a timer lives through real time as in the terminal chat
(advance every few seconds), and the page polls small JSON endpoints:

    GET  /                  the page (chat on the left, the substrate on the right)
    GET  /api/state         now: mode, sleep, gate (coherence, θ, urgency, brake, sources), focus, drives, working memory
    GET  /api/series?min=   the logged steps for charts (v4_steps), with the live state appended
    GET  /api/events?...    new messages and inner events (thoughts said or unspoken, dreams, waking, presence)
    POST /api/send          a message from the user -> the reply
    POST /api/presence      the page is open and visible: the user is here

The page reads; only /api/send and /api/presence act, as typing in the terminal chat and opening it do.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..common.clock import iso
from .drives import NAMES as DRIVES
from .field import at_minute
from .gate import Gate

log = logging.getLogger(__name__)
PAGE = Path(__file__).with_name("web.html")
TICK_SECONDS = 5


def _f(x, d: int = 4):
    return None if x is None or x != x or x in (float("inf"), float("-inf")) else round(float(x), d)


class Live:
    """The agent behind a lock, with the timer that lives through real time."""

    def __init__(self, agent):
        self.agent = agent
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="v4-web-clock", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            with self.lock:
                try:
                    self.agent.advance(self.agent.clock.now())
                    self.agent.substrate.flush()
                except Exception:   # never kill the page from the background
                    log.exception("clock tick failed")

    # ---------- reading ----------

    def state(self) -> dict:
        a = self.agent
        with self.lock:
            s = a.substrate
            f, r, t = s.field, s.last, s.t or 0.0
            wm = []
            for i in s.attention.working_memory(f):
                wm.append({"id": int(f.ids[i]), "kind": f.kind[i], "label": f.label[i][:300], "a": _f(f.a[i], 3),
                           "why": f.describe(i, t), "focus": i in s.attention.focus_set,
                           "unfinished": _f(f.u[i], 2), "refractory": bool(f.refractory_until[i] > t)})
            top = [{"id": int(f.ids[i]), "kind": f.kind[i], "label": f.label[i][:160], "a": _f(f.a[i], 3)}
                   for i in sorted(range(len(f)), key=lambda i: -f.a[i])[:20] if f.a[i] > 0.05]
            return {
                "now": iso(a.clock.now()), "t": iso(at_minute(t)) if s.t else None,
                "mode": s.mode(a._in_conversation()) if s.t else None, "sleep": s.sleep.mode,
                "present": s.present(), "conversation": a._in_conversation(),
                "gate": {"coherence": _f(r.coherence), "energy": _f(r.energy), "stability": _f(r.stability),
                         "theta": _f(r.theta), "urgency": _f(r.urgency), "brake": _f(r.brake),
                         "counted": r.counted, "sources": {k: _f(v, 3) for k, v in r.sources.items()},
                         "u_peak": _f(s.u_peak)},
                "focus": _f(s.attention.focus, 3),
                "drives": {k: _f(v, 3) for k, v in s.drives.x.items()},
                "words": s.drives.words(a._silence_seconds()),
                "wm": wm, "top": top, "field": f.stats(),
                "switches": a.v4_switches.as_dict(),
                "cost": round(a.tracer.totals().get("cost", 0) or 0, 4),
            }

    def series(self, minutes: int) -> dict:
        a = self.agent
        with self.lock:
            a.substrate.flush()
            since = iso(a.clock.now() - timedelta(minutes=minutes))
            rows = a.db.execute("SELECT at, mode, coherence, urgency, brake, focus, drives FROM v4_steps "
                                "WHERE at >= ? ORDER BY rowid", (since,)).fetchall()
        out = {"t": [], "mode": [], "coherence": [], "theta": [], "urgency": [], "brake": [], "focus": [],
               "drives": {k: [] for k in DRIVES}}
        step = max(1, len(rows) // 1500)   # at most ~1500 points per series
        for r in rows[::step]:
            out["t"].append(r["at"])
            out["mode"].append(r["mode"])
            out["coherence"].append(r["coherence"])
            out["urgency"].append(r["urgency"])
            out["brake"].append(None if r["brake"] < 0 else r["brake"])
            out["focus"].append(r["focus"])
            d = json.loads(r["drives"])
            out["theta"].append(round(Gate.theta(d.get("boredom", 0.0), r["mode"]), 4))
            for k in DRIVES:
                out["drives"][k].append(d.get(k))
        return out

    def events(self, after_msg: int, after_firing: int, after_sleep: int, after_att: int) -> dict:
        a = self.agent
        with self.lock:
            a.substrate.flush()
            db = a.db
            if after_msg == 0:   # the first load: the last 200 messages, not the whole history
                after_msg = max(0, (db.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]) - 200)
            msgs = [{"id": r["id"], "at": r["ts"], "role": r["role"], "content": r["content"],
                     "first": bool(r["first"])} for r in db.execute(
                "SELECT m.id, m.ts, m.role, m.content, (o.message_id IS NOT NULL) AS first FROM messages m "
                "LEFT JOIN outbox o ON o.message_id = m.id WHERE m.id > ? ORDER BY m.id", (after_msg,))]
            inner = []
            for r in db.execute("SELECT * FROM v4_firings WHERE id > ? ORDER BY id", (after_firing,)):
                decisions = json.loads(r["decisions"] or "[]")
                writes = [d for d in decisions if d.get("type") == "write"]
                inner.append({"id": r["id"], "at": r["at"], "type": r["kind"], "cause": r["cause"],
                              "said": any(d.get("applied") for d in writes), "thought": r["thought"],
                              "urgency": _f(r["urgency"], 2), "brake": _f(r["brake"], 2),
                              "coherence": _f(r["coherence"], 3), "grew": _f(r["grew_hours"], 1),
                              "unspoken": [{"text": d.get("content"), "why": d.get("note")} for d in writes
                                           if not d.get("applied")],
                              "decisions": [d for d in decisions if d.get("type") not in ("write", "nothing")]})
            sleep = [{"id": r["id"], "at": r["at"], "event": r["event"], "detail": json.loads(r["detail"] or "{}")}
                     for r in db.execute("SELECT * FROM v4_sleep WHERE id > ? AND event IN "
                                         "('onset', 'wake', 'narrative', 'dream') ORDER BY id", (after_sleep,))]
            att = [{"id": r["rowid"], "at": r["at"], "event": r["event"]} for r in db.execute(
                "SELECT rowid, at, event FROM v4_attention WHERE rowid > ? AND event IN ('presence', 'intrusion') "
                "ORDER BY rowid", (after_att,))]
            last_att = db.execute("SELECT COALESCE(MAX(rowid), 0) FROM v4_attention").fetchone()[0]
        return {"messages": msgs, "inner": inner, "sleep": sleep, "attention": att, "last_att": last_att}

    # ---------- acting ----------

    def send(self, text: str) -> dict:
        with self.lock:
            written = self.agent.advance(self.agent.clock.now())
            answer = self.agent.reply(text)
            self.agent.substrate.flush()
        return {"answer": answer, "written_first": written}

    def presence(self) -> None:
        with self.lock:
            if not self.agent.substrate.present():
                self.agent.presence()
            else:   # still here: keep the window open without a new pulse
                s = self.agent.substrate
                from . import constants as K
                s.present_until = s.t + K.PRESENCE_MIN


def make_handler(live: Live):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):   # quiet
            log.debug(fmt, *args)

        def _json(self, data, code: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/":
                    body = PAGE.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif url.path == "/api/state":
                    self._json(live.state())
                elif url.path == "/api/series":
                    self._json(live.series(int(q.get("min", 180))))
                elif url.path == "/api/events":
                    self._json(live.events(*(int(q.get(k, 0)) for k in ("msg", "firing", "sleep", "att"))))
                else:
                    self._json({"error": "not found"}, 404)
            except Exception as e:
                log.exception("GET %s failed", self.path)
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def do_POST(self):
            url = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            try:
                if url.path == "/api/send":
                    text = str(data.get("text") or "").strip()
                    self._json(live.send(text) if text else {"error": "empty"})
                elif url.path == "/api/presence":
                    live.presence()
                    self._json({"ok": True})
                else:
                    self._json({"error": "not found"}, 404)
            except Exception as e:
                log.exception("POST %s failed", self.path)
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    return Handler


def serve(agent, host: str = "127.0.0.1", port: int = 8765) -> None:
    live = Live(agent)
    live.start()
    server = ThreadingHTTPServer((host, port), make_handler(live))
    print(f"alice-v4 web: http://{host}:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        live.stop()
        server.server_close()
        with live.lock:
            agent.close()


__all__ = ["serve", "Live", "time", "datetime"]
