"""The substrate: field, drives, attention, learning, gate and sleep, stepped together in sim time, with no model.

`step()` integrates one dt and returns the events that fell due on the way: a gate firing or a dream (the agent then
calls the wake model), sleep onset, stage changes and waking, the moment for the narrative review, intrusions.
Near-misses and attention switches are logged here. The state is saved into the database at event boundaries.
"""

import json
import math
from dataclasses import dataclass, field as dfield

import numpy as np

from ..common.clock import iso
from . import constants as K
from .attention import Attention
from .config import V4Config
from .drives import Context, Drives
from .field import NEVER, Field, at_minute, minutes
from .gate import Gate, Reading
from .learning import fade, hebbian, pool_duplicates
from .sleep import AWAKE, NREM, REM, SleepCycle, circadian_at, onset_probability

MODES = {"awake": {"input": 1.0, "spread": 1.0, "noise": 1.0, "inhibition": 1.0}, "nrem": K.NREM, "rem": K.REM}


@dataclass
class Event:
    kind: str                       # fire|dream|onset|nrem|rem|wake|narrative|intrusion
    t: float
    reading: Reading | None = None
    coalition: list[int] = dfield(default_factory=list)   # positions
    cause: str = ""
    due: list[int] = dfield(default_factory=list)          # positions of due intention nodes
    grew_hours: float | None = None
    detail: dict = dfield(default_factory=dict)


class Substrate:
    def __init__(self, db, cfg: V4Config, switches, awake_window, may_act_due=lambda t: True):
        """switches: callable -> V4Switches; awake_window: callable(datetime) -> bool (V3's rhythm, used when
        sleep_mode is off); may_act_due: callable(datetime) -> bool, whether something due may be acted on now (V3's
        initiative rules: a reminder at midnight would only be blocked, so it waits)."""
        self.db, self.cfg = db, cfg
        self.switches, self.awake_window = switches, awake_window
        self.may_act_due = may_act_due
        self.field = Field(db)
        self.drives = Drives()
        self.attention = Attention()
        self.gate = Gate(int(round(K.STABILITY_WINDOW_MIN / cfg.dt_min)))
        self.sleep = SleepCycle()
        self.rng = np.random.default_rng(cfg.seed)
        self.t: float | None = None
        self.coactive: dict = {}
        self.novelty = 0.0
        self.engagement = 0.0
        self.unanswered = False
        self.firing_times: list[float] = []        # gate firings and dreams (the emergency ceiling)
        self.u_peak = 0.0                           # max urgency over the last hour (the wish to speak)
        self.present_until = -1e18                  # the user has the chat open (minutes)
        self.ceiling_day: float | None = None       # the sim day the emergency ceiling was last hit
        self.new_edges = 0                          # learned edges since the last sleep (learning_log)
        self.steps = 0
        self.last = Reading()
        self.proximity: dict[int, float] = {}      # intention node position -> proximity to due (set by the agent)
        self.due_nodes: list[int] = []              # due intention nodes not yet acted on (set by the agent)
        self._masks_n = -1
        self._rows: list[tuple] = []
        self._extra: list[tuple] = []

    # ---------- persistence ----------

    def load(self) -> None:
        self.drives.active = self._active_drives()
        self.field.load()
        row = self.db.execute("SELECT value FROM v4_state WHERE key='meta'").fetchone()
        if row is None:
            return
        m = json.loads(row[0])
        ids_to_pos = lambda ids: [self.field.index[i] for i in ids if i in self.field.index]
        self.t = m["t"]
        self.drives.x.update(m["drives"])
        self.attention.focus = m["focus"]
        self.attention.focus_set = ids_to_pos(m["focus_set"])
        self.attention.wm = ids_to_pos(m.get("wm", []))
        self.gate.u = m["u"]
        self.gate.history.extend(frozenset(h) for h in m["history"])
        self.gate.last_near = m.get("last_near", {})
        self.sleep.restore(m["sleep"])
        self.rng.bit_generator.state = m["rng"]
        self.coactive = {(a, b): v for a, b, v in m.get("coactive", [])}
        self.novelty, self.engagement = m.get("novelty", 0.0), m.get("engagement", 0.0)
        self.new_edges = m.get("new_edges", 0)
        self.firing_times, self.steps = m.get("firing_times", []), m.get("steps", 0)
        self.u_peak, self.ceiling_day = m.get("u_peak", 0.0), m.get("ceiling_day")

    def save(self) -> None:
        self.flush()
        self.field.save()
        ids = lambda pos: [int(self.field.ids[i]) for i in pos]
        m = {"t": self.t, "drives": self.drives.x, "focus": self.attention.focus,
             "focus_set": ids(self.attention.focus_set), "wm": ids(self.attention.wm), "u": self.gate.u,
             "history": [sorted(h) for h in self.gate.history], "last_near": self.gate.last_near,
             "sleep": self.sleep.state(), "rng": self.rng.bit_generator.state,
             "coactive": [[a, b, v] for (a, b), v in self.coactive.items()], "novelty": self.novelty,
             "engagement": self.engagement, "new_edges": self.new_edges, "firing_times": [x for x in self.firing_times if x > (self.t or 0) - 2880],
             "u_peak": self.u_peak, "ceiling_day": self.ceiling_day,
             "steps": self.steps}
        self.db.execute("INSERT OR REPLACE INTO v4_state(key, value) VALUES ('meta', ?)", (json.dumps(m),))

    def flush(self) -> None:
        if self._rows:
            self.db.executemany("INSERT INTO v4_steps(at, mode, coherence, urgency, brake, focus, drives, top) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", self._rows)
            self._rows = []
        for sql, args in self._extra:
            self.db.execute(sql, args)
        self._extra = []

    def log(self, sql: str, args: tuple) -> None:
        """Event rows are written with the step rows, in order."""
        self._extra.append((sql, args))

    # ---------- what the dynamics see ----------

    def mode(self, conversation: bool) -> str:
        if conversation:
            return "conversation"
        if self.switches().on("sleep_mode"):
            return self.sleep.mode
        return AWAKE if self.awake_window(at_minute(self.t)) else NREM

    def _active_drives(self) -> set[str]:
        s = self.switches()
        if not s.on("drives"):
            return {"S"}   # sleep as a mode needs sleep pressure, whatever else is fixed
        return set(K.MINIMAL_DRIVES) if self.cfg.drive_set == "minimal" else set(K.DRIVE_BASE)

    def _masks(self) -> None:
        f = self.field
        if self._masks_n == len(f):
            return
        kinds = np.array(f.kind) if len(f) else np.zeros(0, dtype=str)
        self.is_question = kinds == "question"
        self.is_intention = kinds == "intention"
        self.is_trace = kinds == "trace"
        self.sign = np.zeros(len(f))
        self._masks_n = len(f)

    def invalidate(self) -> None:
        self._masks_n = -1

    def set_trace_signs(self, signs: dict[int, float]) -> None:
        self._masks()
        for i, s in signs.items():
            self.sign[i] = np.sign(s)

    def params(self, mode: str) -> dict:
        f = MODES.get(mode, MODES["awake"])
        arousal = self.drives.get("arousal")
        return {"spread": K.SPREAD_GAIN * (0.7 + K.SPREAD_AROUSAL * arousal) * f["spread"],
                "noise": K.NOISE_SIGMA * f["noise"], "input": f["input"],
                "iota": K.INHIBITION_IOTA * self.attention.focus * f["inhibition"],
                "weak_gain": K.REM_WEAK_GAIN if mode == "rem" else 1.0}

    def _proximity_array(self) -> np.ndarray:
        prox = np.full(len(self.field), 0.1)
        for i, p in self.proximity.items():
            if i < len(prox):
                prox[i] = p
        return prox

    def conflict(self) -> tuple[float, np.ndarray]:
        """Opposite-signal traces on the same kind of situation, active together (feeds uncertainty)."""
        f = self.field
        involved = np.zeros(len(f), dtype=bool)
        if not len(f.w):
            return 0.0, involved
        m = self.is_trace[f.ei] & self.is_trace[f.ej] & (f.w >= K.UNCERTAINTY_EDGE) & \
            (self.sign[f.ei] * self.sign[f.ej] < 0)
        if not m.any():
            return 0.0, involved
        involved[f.ei[m]] = True
        involved[f.ej[m]] = True
        # the mean over the conflicting pairs that are active, not the sum: with many traces a sum is always 1
        # (entry 10), scaled up to 1 by how many such pairs there are (one clash is less than three)
        prod = f.a[f.ei[m]] * f.a[f.ej[m]]
        active = prod >= K.CONFLICT_ACTIVE
        if not active.any():
            return 0.0, involved
        return float(prod[active].mean() * min(1.0, active.sum() / K.CONFLICT_FULL)), involved

    def goal(self) -> float:
        open_ = self.is_intention & (self.field.u > 0) & self.field.alive
        return float(1 - math.exp(-np.sum(self.field.u[open_] * self._proximity_array()[open_])))

    def drive_input(self, conflict_nodes: np.ndarray) -> np.ndarray:
        f, d = self.field, self.drives
        v = np.zeros(len(f))
        if (user := f.special("user")) is not None:
            v[user] += K.COUPLE_SOCIAL_USER * d.get("social")
        open_q = self.is_question & (f.u > 0)
        v[open_q] += K.COUPLE_CURIOSITY_QUESTIONS * d.get("curiosity")
        open_i = self.is_intention & (f.u > 0)
        v[open_i] += K.COUPLE_GOAL_INTENTIONS * d.get("goal_tension") * self._proximity_array()[open_i]
        v[conflict_nodes] += K.COUPLE_UNCERTAINTY_TRACES * d.get("uncertainty")
        return v

    def sources(self, coalition: list[int]) -> dict[str, float]:
        f, d = self.field, self.drives
        user = f.special("user")
        questions = [f.a[i] for i in coalition if self.is_question[i] and f.u[i] > 0]
        fresh = [f.salience[i] for i in coalition if not f.own[i] and f.kind[i] not in ("user", "self")
                 and self.t - f.created[i] <= K.FRESH_HOURS * 60]
        on_mind = float(np.mean([f.a[i] for i in coalition])) if coalition else 0.0
        social = d.get("social")
        return {"goal": d.get("goal_tension"),
                # the user node sits outside the focus and is inhibited by it: the need itself counts too
                "social": social * max(f.a[user] if user is not None else 0.0, K.SOCIAL_SELF * social),
                # curiosity about whatever is on its mind, not only about questions it has written down
                "curiosity": d.get("curiosity") * max(float(np.mean(questions)) if questions else 0.0, on_mind),
                "uncertainty": d.get("uncertainty"), "dissonance": d.get("dissonance"),
                "affect": abs(d.get("valence") - d.get("mood")),
                "fresh": float(max(fresh)) if fresh else 0.0}

    def count_ok(self, sources: dict[str, float], coalition: list[int]) -> bool:
        if self.cfg.urgency_count == "nodes":   # Q2: several nodes on one theme count as independent sources
            return any(v >= K.URGENCY_FLOORS[s] for s, v in sources.items()) and \
                sum(1 for i in coalition if self.field.a[i] > K.USE_THRESHOLD) >= K.URGENCY_MIN_KINDS
        return Gate.kinds_ok(sources)

    def ceiling_ok(self, r: Reading, coalition: list[int]) -> bool:
        """The only hard limit (against runaway cost): gate firings and dreams per sim day. Hitting it is logged
        once a day (the chat shows it); it is not part of the dynamics."""
        day = math.floor(self.t / 1440) * 1440
        if sum(1 for x in self.firing_times if x >= day) < K.EMERGENCY_PER_DAY:
            return True
        if self.ceiling_day != day:
            self.ceiling_day = day
            self.log("INSERT INTO v4_firings(at, kind, coherence, urgency, brake, sources, coalition) "
                     "VALUES (?, 'ceiling', ?, ?, ?, ?, ?)",
                     (iso(at_minute(self.t)), r.coherence, r.urgency, r.brake, json.dumps(r.sources),
                      json.dumps([int(self.field.ids[i]) for i in coalition])))
        return False

    def present(self) -> bool:
        return self.t is not None and self.t <= self.present_until

    def presence(self) -> None:
        """The user has opened the chat: the user is here (input to the user node), before saying anything."""
        if (user := self.field.special("user")) is not None:
            kick = np.zeros(len(self.field))
            kick[user] = K.USER_KICK
            self.field.kick(kick, self.t)
        self.drives.pulse("arousal", K.AROUSAL_MESSAGE * (1 - self.drives.get("arousal")))
        self.gate.u += K.PRESENCE_URGENCY * K.BRAKE_B0
        self.present_until = self.t + K.PRESENCE_MIN

    def burst(self) -> list[int]:
        """Waking up is a burst, not a slow start (T45): arousal, open threads, the most salient recent nodes."""
        f = self.field
        self._masks()
        kick = np.zeros(len(f))
        unfinished = (self.is_intention | self.is_question) & (f.u > 0) & f.alive
        kick[unfinished] = K.WAKE_UNFINISHED
        recent = f.alive & (self.t - f.created <= K.WAKE_RECENT_DAYS * 1440) & \
            ~np.isin(np.array(f.kind), ["user", "self"]) & ~unfinished
        top = [int(i) for i in np.argsort(-np.where(recent, f.salience, -1.0))[:K.WAKE_RECENT_N] if recent[i]]
        kick[top] = K.WAKE_RECENT
        f.kick(kick, self.t)
        self.drives.pulse("arousal", K.WAKE_AROUSAL)
        self.gate.u += K.WAKE_URGENCY * K.BRAKE_B0
        return [int(f.ids[i]) for i in np.flatnonzero(kick)]

    def grew_hours(self, coalition: list[int]) -> float | None:
        # the user and self nodes sit above 0.2 for days (social need): they would make every coalition "old"
        rises = [self.field.rise_at[i] for i in coalition
                 if not np.isnan(self.field.rise_at[i]) and self.field.kind[i] not in ("user", "self")]
        return round((self.t - min(rises)) / 60, 3) if rises else None

    def cause(self, coalition: list[int], due: bool) -> str:
        if due:
            return "due"
        f = self.field
        if any(not f.own[i] and f.kind[i] not in ("user", "self") and self.t - f.created[i] <= K.FRESH_HOURS * 60
               for i in coalition):
            return "fresh"
        return "spontaneous"

    # ---------- the step ----------

    def step(self, dt: float, *, conversation: bool, quiet: bool = False) -> list[Event]:
        f, d, s = self.field, self.drives, self.switches()
        self._masks()
        t = self.t
        mode = self.mode(conversation)
        d.active = self._active_drives()
        p = self.params(mode)
        conflict, conflict_nodes = self.conflict()
        f.step(t, dt, p, self.drive_input(conflict_nodes), self.attention.outside_focus(f), self.rng)
        events: list[Event] = []
        t1 = t + dt
        if s.on("intrusions") and mode in (AWAKE, REM, "conversation") and len(f):
            if (i := f.intrusion(self.rng, t, dt, d.get("boredom"), self.attention.focus)) is not None:
                events.append(Event("intrusion", t1, coalition=[i]))
                self.log("INSERT INTO v4_attention(at, event, focus, energy, coalition) VALUES (?, 'intrusion', ?, ?, ?)",
                         (iso(at_minute(t1)), self.attention.focus, float(f.a[i]), json.dumps([int(f.ids[i])])))
        if mode == NREM and s.on("sleep_mode") and (i := self.sleep.next_replay(f, t)) is not None:
            kick = np.zeros(len(f))
            kick[i] = K.REPLAY_KICK
            f.kick(kick, t1)
        f.record_uses(t1)
        self.steps += 1
        if self.steps % K.BASE_EVERY_STEPS == 0 or not np.isfinite(f.B).any():
            f.update_base(t1)
        if self.attention.update(f, dt, d.get("arousal")):
            self.log("INSERT INTO v4_attention(at, event, focus, energy, coalition) VALUES (?, 'switch', ?, ?, ?)",
                     (iso(at_minute(t1)), self.attention.focus, Attention.energy(f, self.attention.focus_set),
                      json.dumps([int(f.ids[i]) for i in self.attention.focus_set])))
        self.new_edges += hebbian(f, self.attention.wm, dt, K.NREM_HEBB_GAIN if mode == NREM else 1.0, self.coactive,
                                  t1)
        if self.steps % 60 == 0:
            fade(f, 60 * dt, mode == NREM)
        wm = self.attention.wm
        ctx = Context(asleep=mode in (NREM, REM), conversation=conversation, novelty=self.novelty,
                      activity=float(np.mean(f.a[wm])) if wm else 0.0, conflict=conflict, goal=self.goal(),
                      open_questions=int((self.is_question & (f.u > 0)).sum()), unanswered=self.unanswered,
                      engagement=self.engagement)
        d.step(dt, ctx, self.rng)
        self.novelty *= math.exp(-dt / 60)

        coalition = self.attention.focus_set
        sources = self.sources(coalition)
        r = self.gate.step(dt, f, coalition, sources, self.count_ok(sources, coalition), d.get("fatigue"), d.get("S"),
                           d.get("boredom"), mode)
        self.last = r
        self.u_peak = max(r.urgency, self.u_peak * math.exp(-dt / K.SPEECH_PEAK_MIN))
        self.t = t1
        if not quiet and s.on("gate"):
            events += self._gate_events(r, mode, coalition)
        if not quiet and not conversation and s.on("sleep_mode"):
            events += self._sleep_events(dt, mode)
        if self.steps % K.LOG_EVERY_STEPS == 0:
            self._rows.append((iso(at_minute(t1)), mode, round(r.coherence, 4), round(r.urgency, 4),
                               -1.0 if r.brake == float("inf") else round(r.brake, 4), round(self.attention.focus, 4),
                               json.dumps({k: round(v, 4) for k, v in d.x.items()}), json.dumps(f.top())))
        return events

    def _gate_events(self, r: Reading, mode: str, coalition: list[int]) -> list[Event]:
        # a due intention fires on its own, again after its refractory period if nothing came of it
        due = [i for i in self.due_nodes if i < len(self.field) and self.field.refractory_until[i] <= self.t]
        if mode == AWAKE and due and self.may_act_due(at_minute(self.t)) and self.ceiling_ok(r, coalition):
            kick = np.zeros(len(self.field))
            kick[due] = K.DUE_KICK
            self.field.kick(kick, self.t)
            self.gate.u = max(self.gate.u, r.brake)   # enough to fire
            r.urgency = self.gate.u
            group = list(dict.fromkeys(due + coalition))
            return [Event("fire", self.t, r, group, "due", due, self.grew_hours(group))]
        if r.coherent and r.urgent:
            if mode in (AWAKE, "conversation") and self.ceiling_ok(r, coalition):
                return [Event("fire", self.t, r, list(coalition), self.cause(coalition, False), [],
                              self.grew_hours(coalition))]
            if mode == REM and self.sleep.dreams < K.DREAMS_PER_NIGHT and self.ceiling_ok(r, coalition):
                return [Event("dream", self.t, r, list(coalition), "dream", [], self.grew_hours(coalition))]
        if (kind := self.gate.near_miss(r, self.t)) is not None:
            self.log("INSERT INTO v4_firings(at, kind, coherence, urgency, brake, sources, coalition) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (iso(at_minute(self.t)), kind, r.coherence, r.urgency, r.brake, json.dumps(r.sources),
                      json.dumps([int(self.field.ids[i]) for i in coalition])))
        return []

    def _sleep_events(self, dt: float, mode: str) -> list[Event]:
        d, t = self.drives, self.t
        if self.sleep.mode == AWAKE:
            u_norm = min(1.0, self.gate.u / K.BRAKE_B0)
            p = onset_probability(dt, d.get("S"), circadian_at(t), d.get("arousal"), u_norm)
            if self.rng.random() < p:
                self.sleep.fall_asleep(self.field, t, self.rng)
                return [Event("onset", t, detail={"S": round(d.get("S"), 3), "replay": len(self.sleep.replay)})]
            return []
        out = []
        stage = self.sleep.phase(t)
        if stage == REM and self.sleep.cycle == 0 and not self.sleep.narrative_done:
            self.sleep.narrative_done = True
            out.append(Event("narrative", t))
        if stage:
            out.append(Event(stage, t, detail={"cycle": self.sleep.cycle}))
        if self.sleep.should_wake(t, d.get("S")):
            out.append(self.wake("rested"))
        return out

    def wake(self, reason: str) -> Event:
        slept = (self.t - self.sleep.onset_at) / 60 if self.sleep.onset_at is not None else None
        self.sleep.wake(self.t)
        return Event("wake", self.t, detail={"reason": reason, "slept_hours": round(slept, 2) if slept else None})

    def after_fire(self, event: Event) -> None:
        """A thought consumes what triggered it: urgency resets, the coalition is held down for a while, fatigue."""
        self.gate.reset()
        for i in event.coalition:
            self.field.refractory_until[i] = self.t + K.REFRACTORY_MIN
        self.drives.pulse("fatigue", K.FATIGUE_PER_FIRING)
        # a thought partly answers what drove it: curiosity, uncertainty and dissonance it was about ease (entry 10)
        if event.kind == "fire" and event.reading is not None:
            for name, share in K.SATIATION.items():
                if event.reading.sources.get(name, 0.0) >= K.URGENCY_FLOORS[name]:
                    self.drives.set(name, self.drives.get(name) * (1 - share))
        self.firing_times.append(self.t)
        if event.kind == "dream":
            self.sleep.dreams += 1

    def fall_asleep_now(self) -> Event:
        self.sleep.fall_asleep(self.field, self.t, self.rng)
        return Event("onset", self.t, detail={"forced": True})

    def prune_and_count(self) -> dict:
        """Once a day (at sleep onset): edges that have faded away are removed; what was learned is logged."""
        out = {"created": self.new_edges, "pruned": self.field.prune(K.EDGE_PRUNE), "edges": len(self.field.w)}
        self.new_edges = 0
        return out

    def pool(self) -> int:
        since = self.sleep.last_wake if self.sleep.last_wake is not None else self.t - 1440
        day = [i for i in range(len(self.field)) if self.field.created[i] > since and self.field.alive[i]]
        return pool_duplicates(self.field, day)


def start_minute(t) -> float:
    return minutes(t)


__all__ = ["Substrate", "Event", "NEVER"]
