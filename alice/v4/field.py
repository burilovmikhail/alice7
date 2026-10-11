"""The activation field (spec §6.1, §6.2): nodes, sparse symmetric edges, the activation step, intrusions.

One node per V1 memory, V3 thought, intention, open question and experience trace, plus the user and the agent
itself. Everything here is numeric and local; no model is called and nothing a model wrote sets a number. Arrays are
indexed by position; `index` maps node ids to positions. The whole state is saved into v4_state as one npz blob.
"""

import io
import json
from datetime import datetime, timedelta

import numpy as np

from ..common.clock import iso
from . import constants as K

EPOCH = datetime(2000, 1, 1)
NEVER = -1e18

# How a node is named for the model (spec §6.6)
KIND_LABEL = {
    "memory": "something the user told you",
    "episode": "something that happened",
    "thought": "something you thought before",
    "dream": "a dream you had",
    "intention": "something you meant to do",
    "question": "a question you keep coming back to",
    "trace": "how the user took something you said",
    "event": "something that happened in a conversation",
    "passage": "a text the user shared with you",
    "user": "the user",
    "self": "you",
}
INTRUSION_LABEL = "came to mind for no clear reason"


def minutes(t: datetime) -> float:
    return (t - EPOCH).total_seconds() / 60


def at_minute(m: float) -> datetime:
    return (EPOCH + timedelta(minutes=m)).replace(microsecond=0)


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def _vec(blob) -> np.ndarray | None:
    return np.frombuffer(blob, dtype=np.float32).copy() if blob else None


class Field:
    FLOAT_ARRAYS = ("a", "xi", "tau", "valence", "arousal_tag", "u", "salience", "created", "last_considered",
                    "refractory_until", "intrusion_until", "rise_at", "last_use", "B")

    def __init__(self, db):
        self.db = db
        self.ids = np.zeros(0, dtype=np.int64)
        self.kind: list[str] = []
        self.ref: list[int | None] = []
        self.label: list[str] = []
        self.own = np.zeros(0, dtype=bool)
        self.alive = np.zeros(0, dtype=bool)
        for name in self.FLOAT_ARRAYS:
            setattr(self, name, np.zeros(0))
        self.uses: list[list[float]] = []
        self.emb: np.ndarray | None = None
        self.ei = np.zeros(0, dtype=np.int64)
        self.ej = np.zeros(0, dtype=np.int64)
        self.w = np.zeros(0)
        self.w0 = np.zeros(0)
        self.edge_at: dict[tuple[int, int], int] = {}
        self.index: dict[int, int] = {}
        self.by_ref: dict[tuple[str, int], int] = {}

    def __len__(self) -> int:
        return len(self.ids)

    # ---------- nodes ----------

    def node_for(self, kind: str, ref: int | None) -> int | None:
        return self.by_ref.get((kind, ref)) if ref is not None else None

    def special(self, kind: str) -> int | None:
        return self.by_ref.get((kind, 0))

    def mask(self, *kinds: str) -> np.ndarray:
        kinds = set(kinds)
        return np.array([k in kinds for k in self.kind], dtype=bool) & self.alive if len(self) else np.zeros(0, bool)

    def similarities(self, vec: np.ndarray | None) -> np.ndarray:
        """Cosine to every node (0 for nodes without a vector, and for dead nodes)."""
        if vec is None or self.emb is None or not len(self) or self.emb.shape[1] != len(vec):
            return np.zeros(len(self))
        return (self.emb @ vec) * self.alive

    def add_node(self, kind: str, ref: int | None, label: str, *, now: datetime, embedding: np.ndarray | None,
                 source: str = "external", valence: float = 0.0, arousal_tag: float = 0.0, u: float = 0.0,
                 salience: float = 0.0, a0: float = 0.0, uses: int = 0, similar_edges: bool = True) -> int:
        """A new node, with edges to the most similar existing ones (spec §6.1). Returns its position."""
        sims = self.similarities(embedding) if similar_edges else np.zeros(len(self))
        node_id = self.db.execute(
            "INSERT INTO v4_nodes(kind, ref_id, label, source, created_at, embedding) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref, label[:2000], source, iso(now),
             embedding.astype(np.float32).tobytes() if embedding is not None else None)).lastrowid
        i = len(self)
        t = minutes(now)
        self.ids = np.append(self.ids, node_id)
        self.kind.append(kind)
        self.ref.append(ref)
        self.label.append(label)
        self.own = np.append(self.own, source == "own")
        self.alive = np.append(self.alive, True)
        values = {"a": a0, "xi": 0.0, "tau": K.TAU_MIN * (1 + K.TAU_AROUSAL_GAIN * max(0.0, arousal_tag)),
                  "valence": valence, "arousal_tag": arousal_tag, "u": u, "salience": salience, "created": t,
                  "last_considered": t, "refractory_until": NEVER, "intrusion_until": NEVER,
                  "rise_at": t if a0 >= 0.2 else np.nan, "last_use": NEVER, "B": -np.inf}
        for name, v in values.items():
            setattr(self, name, np.append(getattr(self, name), v))
        self.uses.append([t] * uses)
        self._append_vector(embedding)
        self.index[node_id] = i
        if ref is not None:
            self.by_ref[(kind, ref)] = i
        if similar_edges and len(sims):
            order = np.argsort(-sims)[:K.EDGE_TOP_K]
            self.add_edges([(int(j), i, float((sims[j] - K.EDGE_MIN_COS) / (1 - K.EDGE_MIN_COS)))
                            for j in order if sims[j] >= K.EDGE_MIN_COS])
        return i

    def _append_vector(self, vec: np.ndarray | None) -> None:
        if self.emb is None:
            if vec is None:
                return
            self.emb = np.zeros((len(self) - 1, len(vec)), dtype=np.float32)
        row = vec.astype(np.float32) if vec is not None and len(vec) == self.emb.shape[1] else \
            np.zeros(self.emb.shape[1], dtype=np.float32)
        self.emb = np.vstack([self.emb, row[None, :]])

    def kill(self, i: int) -> None:
        """A superseded memory, a closed thread: it stays (nothing is deleted) but takes no further part."""
        self.alive[i] = False
        self.a[i] = 0.0
        self.u[i] = 0.0

    # ---------- edges ----------

    def add_edges(self, edges: list[tuple[int, int, float]], *, learned: bool = False) -> int:
        """Symmetric edges; an existing edge keeps the stronger weight. `learned` edges start at w0 = 0 (they did
        not exist at creation: reset_weights removes them). Returns the number of new edges."""
        new_i, new_j, new_w = [], [], []
        for i, j, w in edges:
            if i == j:
                continue
            key = (min(i, j), max(i, j))
            w = float(min(1.0, max(0.0, w)))
            if key in self.edge_at:
                k = self.edge_at[key]
                if w > self.w[k]:
                    self.w[k] = w
                    if not learned:
                        self.w0[k] = max(self.w0[k], w)
                continue
            self.edge_at[key] = len(self.w) + len(new_w)
            new_i.append(key[0])
            new_j.append(key[1])
            new_w.append(w)
        if new_w:
            self.ei = np.concatenate([self.ei, np.array(new_i, dtype=np.int64)])
            self.ej = np.concatenate([self.ej, np.array(new_j, dtype=np.int64)])
            self.w = np.concatenate([self.w, np.array(new_w)])
            self.w0 = np.concatenate([self.w0, np.zeros(len(new_w)) if learned else np.array(new_w)])
        return len(new_w)

    def weight(self, i: int, j: int) -> float:
        k = self.edge_at.get((min(i, j), max(i, j)))
        return float(self.w[k]) if k is not None else 0.0

    def neighbors(self, i: int, min_w: float = 0.0) -> list[int]:
        m = ((self.ei == i) | (self.ej == i)) & (self.w >= min_w)
        return [int(x) for x in np.where(self.ei[m] == i, self.ej[m], self.ei[m])]

    def prune(self, below: float) -> int:
        """Remove edges that have faded under `below`. Returns how many."""
        keep = self.w >= below
        removed = int((~keep).sum())
        if removed:
            self.ei, self.ej, self.w, self.w0 = self.ei[keep], self.ej[keep], self.w[keep], self.w0[keep]
            self.edge_at = {(int(i), int(j)): k for k, (i, j) in enumerate(zip(self.ei, self.ej))}
        return removed

    # ---------- dynamics ----------

    def spreading(self, a: np.ndarray, weak_gain: float = 1.0) -> np.ndarray:
        """Σ_j w_ij · f(a_j), f = sigmoid(8·(a − 0.4)), divided by max(1, Σ_j w_ij); in REM weak edges count more.
        (The normalization is not in the spec's formula: without it, Hebbian growth makes any coalition a permanent
        attractor at a = 1. See specs/v4/tuning-log.md, entry 0.)"""
        if not len(self.w):
            return np.zeros(len(a))
        fa = sigmoid(K.SPREAD_SLOPE * (a - K.SPREAD_MID)) * self.alive
        w = self.w if weak_gain == 1.0 else np.where(self.w < K.REM_WEAK_EDGE, self.w * weak_gain, self.w)
        n = len(a)
        total = np.bincount(self.ei, weights=w * fa[self.ej], minlength=n) + \
            np.bincount(self.ej, weights=w * fa[self.ei], minlength=n)
        if not K.SPREAD_NORMALIZE:
            return total
        degree = np.bincount(self.ei, weights=w, minlength=n) + np.bincount(self.ej, weights=w, minlength=n)
        return total / np.maximum(1.0, degree)

    def derivative(self, a: np.ndarray, t: float, p: dict, drive_input: np.ndarray, outside_focus: np.ndarray,
                   noise: np.ndarray | None) -> np.ndarray:
        """da/dt of spec §6.2, for activations `a` at time `t` (minutes). `p`: gains for the mode."""
        input_scale = np.where(self.own, K.OWN_INPUT, 1.0)
        spread = p["spread"] * self.spreading(a, p.get("weak_gain", 1.0))
        resting = K.RESTING_BETA * sigmoid(self.B)
        hours = np.maximum(0.0, t - self.last_considered) / 60
        tug = self.u * K.TUG_MAX * (1 - 0.5 ** (hours / K.TUG_REST_H))
        inhibition = p["iota"] * K.INHIBITION_RATE * a * outside_focus
        refractory = K.REFRACTORY_RATE * a * (self.refractory_until > t)
        da = -a / self.tau + input_scale * (spread + drive_input) + resting + tug - inhibition - refractory
        if noise is not None:
            da = da + p["noise"] * noise
        return da * self.alive

    def step(self, t: float, dt: float, p: dict, drive_input: np.ndarray, outside_focus: np.ndarray,
             rng: np.random.Generator | None) -> None:
        """One Euler step; the Ornstein–Uhlenbeck noise advances with it."""
        if not len(self):
            return
        if rng is not None:
            self.xi += -self.xi * dt / K.NOISE_TAU + np.sqrt(2 * dt / K.NOISE_TAU) * rng.standard_normal(len(self))
        before = self.a
        self.a = np.clip(self.a + dt * self.derivative(self.a, t, p, drive_input, outside_focus,
                                                       self.xi if rng is not None else None), 0.0, 1.0)
        rising = (before < 0.2) & (self.a >= 0.2)
        self.rise_at = np.where(rising, t + dt, np.where(self.a < 0.2, np.nan, self.rise_at))

    def preview(self, t: float, minutes_: float, dt: float, p: dict, drive_input: np.ndarray,
                outside_focus: np.ndarray) -> np.ndarray:
        """The activations after `minutes_` more of the same dynamics, without noise and without touching the
        state (recall ranks by this: the message's input has spread, spec §6.11)."""
        a = self.a.copy()
        for k in range(int(round(minutes_ / dt))):
            a = np.clip(a + dt * self.derivative(a, t + k * dt, p, drive_input, outside_focus, None), 0.0, 1.0)
        return a

    def kick(self, amounts: np.ndarray, t: float) -> None:
        """External input arriving at once (a message, replay, an intrusion)."""
        before = self.a
        self.a = np.clip(self.a + amounts * self.alive, 0.0, 1.0)
        self.rise_at = np.where((before < 0.2) & (self.a >= 0.2), t, self.rise_at)

    def intrusion(self, rng: np.random.Generator, t: float, dt: float, boredom: float, focus: float) -> int | None:
        """A Poisson process picks an old node, weighted by salience and age, and gives it a kick (T47–T52)."""
        rate = K.INTRUSION_RATE_PER_H / 60 * (1 + 2 * boredom) * (1 - focus)
        if not len(self) or rng.random() >= rate * dt:
            return None
        age_h = (t - self.created) / 60
        old = self.alive & (age_h >= K.INTRUSION_MIN_AGE_H) & (self.a < K.WM_THRESHOLD) & \
            ~np.isin(np.array(self.kind), ["user", "self"])
        if not old.any():
            return None
        weights = np.where(old, (0.1 + self.salience) * (1 + np.log1p(np.maximum(age_h, 0) / 24)), 0.0)
        i = int(rng.choice(len(self), p=weights / weights.sum()))
        self.a[i] = min(1.0, self.a[i] + K.INTRUSION_KICK)
        self.intrusion_until[i] = t + K.INTRUSION_MARK_MIN
        if np.isnan(self.rise_at[i]):
            self.rise_at[i] = t
        return i

    # ---------- base-level activation (ACT-R, §6.8) ----------

    def record_uses(self, t: float) -> None:
        """A use when activation crosses 0.5 upward, and again every hour it stays above."""
        due = (self.a >= K.USE_THRESHOLD) & (t - self.last_use >= K.USE_REPEAT_MIN)
        for i in np.flatnonzero(due):
            self.use(int(i), t)

    def use(self, i: int, t: float) -> None:
        self.uses[i].append(t)
        if len(self.uses[i]) > K.USES_KEPT:
            del self.uses[i][:-K.USES_KEPT]
        self.last_use[i] = t

    def update_base(self, t: float) -> None:
        B = np.full(len(self), -np.inf)
        for i, uses in enumerate(self.uses):
            if uses:
                hours = np.maximum((t - np.array(uses)) / 60, 1 / 60)
                B[i] = np.log(np.sum(hours ** -K.BASE_DECAY))
        self.B = B

    # ---------- persistence ----------

    def save(self) -> None:
        buf = io.BytesIO()
        lengths = np.array([len(u) for u in self.uses], dtype=np.int64)
        flat = np.array([x for u in self.uses for x in u], dtype=np.float64)
        np.savez(buf, ids=self.ids, own=self.own, alive=self.alive, ei=self.ei, ej=self.ej, w=self.w, w0=self.w0,
                 use_lengths=lengths, use_flat=flat, **{n: getattr(self, n) for n in self.FLOAT_ARRAYS})
        self.db.execute("INSERT OR REPLACE INTO v4_state(key, value) VALUES ('field', ?)", (buf.getvalue(),))

    def load(self) -> None:
        rows = self.db.execute("SELECT * FROM v4_nodes ORDER BY id").fetchall()
        blob = self.db.execute("SELECT value FROM v4_state WHERE key='field'").fetchone()
        saved = dict(np.load(io.BytesIO(blob[0]))) if blob else {}
        pos = {int(n): k for k, n in enumerate(saved.get("ids", []))}
        vectors = [_vec(r["embedding"]) for r in rows]
        dim = next((len(v) for v in vectors if v is not None), None)
        self.__init__(self.db)
        self.ids = np.array([r["id"] for r in rows], dtype=np.int64)
        self.kind = [r["kind"] for r in rows]
        self.ref = [r["ref_id"] for r in rows]
        self.label = [r["label"] for r in rows]
        n = len(rows)
        take = [pos.get(int(r["id"])) for r in rows]   # a node saved without its numbers (a crash) gets defaults

        def column(name, default, dtype=float):
            src = saved.get(name)
            return np.array([src[k] if k is not None and src is not None else default for k in take], dtype=dtype)

        self.own = np.array([r["source"] == "own" for r in rows], dtype=bool)
        self.alive = column("alive", True, bool)
        created = np.array([minutes(datetime.fromisoformat(r["created_at"])) for r in rows])
        defaults = {"a": 0.0, "xi": 0.0, "tau": K.TAU_MIN, "valence": 0.0, "arousal_tag": 0.0, "u": 0.0,
                    "salience": 0.0, "created": None, "last_considered": None, "refractory_until": NEVER,
                    "intrusion_until": NEVER, "rise_at": np.nan, "last_use": NEVER, "B": -np.inf}
        for name, d in defaults.items():
            col = column(name, np.nan if d is None else d)
            if d is None:
                col = np.where(np.isnan(col), created, col)
            setattr(self, name, col)
        lengths, flat = saved.get("use_lengths"), saved.get("use_flat")
        offsets = np.concatenate([[0], np.cumsum(lengths)]) if lengths is not None else None
        self.uses = [list(flat[offsets[k]:offsets[k + 1]]) if k is not None and offsets is not None else []
                     for k in take]
        if dim is not None:
            self.emb = np.stack([v if v is not None and len(v) == dim else np.zeros(dim, np.float32) for v in vectors]) \
                if n else np.zeros((0, dim), np.float32)
        self.index = {int(r["id"]): k for k, r in enumerate(rows)}
        self.by_ref = {(r["kind"], r["ref_id"]): k for k, r in enumerate(rows) if r["ref_id"] is not None}
        if "ei" in saved:
            back = {int(saved["ids"][k]): self.index.get(int(saved["ids"][k])) for k in range(len(saved["ids"]))}
            ei = np.array([back[int(saved["ids"][x])] for x in saved["ei"]], dtype=np.int64)
            ej = np.array([back[int(saved["ids"][x])] for x in saved["ej"]], dtype=np.int64)
            self.ei, self.ej, self.w, self.w0 = ei, ej, saved["w"].astype(float), saved["w0"].astype(float)
            self.edge_at = {(int(i), int(j)): k for k, (i, j) in enumerate(zip(self.ei, self.ej))}

    def describe(self, i: int, t: float) -> str:
        """A node's kind in words, for the model (spec §6.6)."""
        if self.intrusion_until[i] > t:
            return INTRUSION_LABEL
        return KIND_LABEL.get(self.kind[i], self.kind[i])

    def top(self, n: int = K.FIELD_TOP_N) -> list[list]:
        if not len(self):
            return []
        order = np.argsort(-self.a)[:n]
        return [[int(self.ids[i]), round(float(self.a[i]), 3)] for i in order if self.a[i] > 0.01]

    def stats(self) -> dict:
        kinds: dict[str, int] = {}
        for k, alive in zip(self.kind, self.alive):
            if alive:
                kinds[k] = kinds.get(k, 0) + 1
        return {"nodes": int(self.alive.sum()), "edges": int(len(self.w)), "learned_edges": int((self.w0 == 0).sum()),
                "kinds": kinds}


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False)
