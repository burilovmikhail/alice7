"""V4 agent: V3 plus continuous cognitive dynamics (spec specs/v4/continuous-cognitive-dynamics.md).

AgentV4 subclasses the frozen AgentV3 (D1). A numerical substrate (field, drives, attention, learning, gate, sleep)
lives in sim time without any model; it is changed by experience through local rules and decides what the language
model sees and when it is called. Experience writes it (messages, V1's extracted memories, reactions, appraisals,
time, replay, the agent's own thoughts at 0.3); the self-narrative, the reply model and the operator only read it
(§4.3, D5). With every V4 switch off, V4 sends every model exactly what V3 sends.
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from ..common.clock import Clock, iso
from ..common.config import Config
from ..common.db import get_meta, set_meta
from ..v1.agent import AgentV1
from ..v1.session import Session
from ..v2.reflector import last_call_id
from ..v2.switches import NAMES as V2_NAMES
from ..v3 import rhythm
from ..v3.affect import THOUGHT_WEIGHT, clamp
from ..v3.agent import AgentV3, DUE_ACTED
from ..v3.switches import NAMES as V3_NAMES
from ..v3.thoughts import OwnTimeMechanism
from . import constants as K
from .actions import ActionSelector, InitiativeV4
from .attention import Attention
from .config import V4Config, load_v4_config
from .context import (WOKE_KEY, ContextV4, HowYouAreMechanism, JustThoughtMechanism, WokeMechanism,
                      WorkingMemoryMechanism)
from .field import at_minute, minutes
from .grip import GripMechanism, assess
from .episodes import Episodes, EpisodesMechanism, RECENT
from ..common.timeparse import parse_time_range
from ..v1.retrieval import search
from .learning import expected_signal, reconsolidate, salience, salience_parts
from .narrative import NarrativeMechanism, Narrator
from .recall import recall
from .schema import ensure_schema
from .substrate import Event, Substrate
from .switches import NAMES as V4_NAMES
from .switches import V4Switches
from .traces import TraceStore, TracesMechanism, TurnObserverV4
from .verbalize import Verbalizer

log = logging.getLogger(__name__)

ABLATION_KEY = "v4_ablation"       # meta: fork-time removals (E15): ["episodic", "traces"]
DREAMS_KEY = "v4_dreams_tonight"   # meta: tonight's dreams, for the waking context
NEXT_STREAM = "v4_next_stream"     # meta: V3's next stream tick, when the gate is off
NEXT_SLEEP = "v4_next_v3_sleep"    # meta: V3's next nightly sleep, when sleep_mode is off
FIELD_OPS = ("reset_activations", "reset_weights", "remove_episodic", "remove_traces", "rebuild_similarity")
STRUCTURAL_W = (K.LINK_WEIGHT, K.TRACE_WEIGHT, K.THOUGHT_WEIGHT, K.COMMITMENT_USER_WEIGHT, K.OWN_LINK_WEIGHT,
                K.EVENT_CHAIN_W, K.EVENT_CHAIN_W / 2, K.EVENT_FACT_W, K.DUPLICATE_W)


class AgentV4(AgentV3):
    name = "V4"

    def __init__(self, cfg: Config, clock: Clock, db_path: Path | str | None = None, *, v4: V4Config | None = None,
                 v4_switches: V4Switches | None = None, **kwargs):
        """v4_switches: explicit build-time V4 switches; otherwise the ones this database was created with, otherwise
        V4Config's. V2's and V3's switches work as before."""
        self.v4 = v4 or load_v4_config()
        self._v4_ready = False
        self._pending_finalize: list[int] = []
        self._turn: dict = {}
        super().__init__(cfg, clock, db_path, **kwargs)
        ensure_schema(self.db)
        stored = get_meta(self.db, "v4_switches")
        if v4_switches is None:
            v4_switches = V4Switches(**json.loads(stored)) if stored else self.v4.switches
        if stored is None:
            set_meta(self.db, "v4_switches", json.dumps(v4_switches.as_dict()))
        self.v4_switches = v4_switches
        self.traces = TraceStore(self.store)
        self.episodes = Episodes(self)
        self.turn_observer_v4 = TurnObserverV4(self.store, self.affect, self.later, self.llm, self.models["observe"])
        self.substrate = Substrate(self.db, self.v4, lambda: self.v4_switches, lambda t: rhythm.awake(t, self.v3))
        self.verbalizer = Verbalizer(self, self.llm, self.v3_models["wake"])
        self.actions = ActionSelector(self)
        self.initiative = InitiativeV4(self, self.v3)
        self.narrator = Narrator(self, self.v3_models["wake"], self.models["observe"])
        self.context = ContextV4(self, self.store, cfg, clock, self.context.persona, self.active_mechanisms)
        self._v4_mechanisms = {
            "narrative": NarrativeMechanism(self.selfmodel, self._mechanisms["selfmodel"].review, lambda: self.switches),
            "how": HowYouAreMechanism(self), "mind": WorkingMemoryMechanism(self), "traces": TracesMechanism(self),
            "woke": WokeMechanism(self), "grip": GripMechanism(self), "episodes": EpisodesMechanism(self),
            "just": JustThoughtMechanism(self),
            "own_time": OwnTimeMechanism(lambda: True, lambda: self.v3_switches.initiative)}
        self._last_hour = None
        self._v4_ready = True
        if self.v4_switches.field:
            self._start_field()
        for sid in self._pending_finalize:   # sessions closed while loading, before V4 was set up
            self._finalize(sid)
        self._pending_finalize = []

    # ---------- switches ----------

    @property
    def field_on(self) -> bool:
        return getattr(self, "_v4_ready", False) and self.v4_switches.field

    def _ablated(self, what: str) -> bool:
        return what in set(json.loads(get_meta(self.db, ABLATION_KEY) or "[]"))

    def active_mechanisms(self) -> list:
        if not self.field_on:
            return super().active_mechanisms()
        s, out = self.v4_switches, []
        for name, m in self._mechanisms.items():
            if not getattr(self.switches, name):
                continue
            if name == "lessons" and s.on("traces"):
                continue   # traces replace lessons
            if name == "intentions":
                if self._later_on():
                    continue   # V3 intentions come up through working memory
            if name == "selfmodel" and s.on("narrative"):
                m = self._v4_mechanisms["narrative"]
            out.append(m)
        if s.on("drives"):
            out.append(self._v4_mechanisms["how"])
        elif self.v3_switches.affect:
            out.append(self._v3_mechanisms["affect"])
        out.append(self._v4_mechanisms["own_time"])
        if not s.on("gate") and self.v3_switches.lives_in_silence:
            out.append(self._v3_mechanisms["thoughts"])   # V3's stream runs instead of the gate
        out.append(self._v4_mechanisms["mind"])
        out.append(self._v4_mechanisms["episodes"])
        if s.on("gate"):
            out.append(self._v4_mechanisms["just"])
        if s.on("grip"):
            out.append(self._v4_mechanisms["grip"])
        if s.on("traces"):
            out.append(self._v4_mechanisms["traces"])
        if s.on("sleep_mode"):
            out.append(self._v4_mechanisms["woke"])
        elif self.v3_switches.sleep:
            out.append(self._v3_mechanisms["sleep"])
        return out

    def apply_switches(self, changes: dict[str, bool]) -> None:
        """Probe-time ablation of V2, V3 and V4 mechanisms alike (forks only)."""
        if unknown := set(changes) - set(V2_NAMES) - set(V3_NAMES) - set(V4_NAMES):
            raise ValueError(f"unknown switch(es): {', '.join(sorted(unknown))}")
        if older := {k: v for k, v in changes.items() if k not in V4_NAMES}:
            super().apply_switches(older)
        if v4 := {k: v for k, v in changes.items() if k in V4_NAMES}:
            was = self.v4_switches.field
            self.v4_switches = self.v4_switches.with_(v4)
            self.substrate.drives.active = self.substrate._active_drives()
            if self.v4_switches.field and not was:
                self._start_field()

    def manipulate(self, ops) -> dict:
        """Probe-time changes to the substrate on a fork (spec §9.2): reset_activations, reset_weights (edges back
        to their weight at creation, learned edges removed, base levels cleared), remove_episodic and remove_traces
        (E15: hidden from recall and the prompt; the traces' nodes stay in the field)."""
        ops = [ops] if isinstance(ops, str) else list(ops)
        if unknown := set(ops) - set(FIELD_OPS):
            raise ValueError(f"unknown field operation(s): {', '.join(sorted(unknown))}")
        if not self.field_on:
            return {"ignored": ops}
        f, s = self.substrate.field, self.substrate
        if "reset_activations" in ops:
            f.a[:] = 0.0
            f.xi[:] = 0.0
            f.rise_at[:] = np.nan
            s.attention = Attention()
            s.gate.reset()
            s.gate.history.clear()
        if "reset_weights" in ops:
            f.w = f.w0.copy()
            f.prune(1e-9)
            f.uses = [[] for _ in f.uses]
            f.B = np.full(len(f), -np.inf)
            s.coactive = {}
        if "rebuild_similarity" in ops:   # similarity edges made under an older threshold (entry 10)
            dropped = self._rebuild_similarity()
            log.info("rebuild_similarity: %s edges dropped", dropped)
        removed = set(json.loads(get_meta(self.db, ABLATION_KEY) or "[]"))
        removed |= {op.removeprefix("remove_") for op in ops if op.startswith("remove_")}
        set_meta(self.db, ABLATION_KEY, json.dumps(sorted(removed)))
        s.save()
        return {"applied": ops}

    def _rebuild_similarity(self) -> int:
        """Keep structural edges (links, chains, traces to the user, thoughts to their coalition: their weights at
        creation are fixed constants), edges to nodes without vectors, and learned ones; similarity edges are kept
        only above today's threshold, re-weighted. Returns how many were dropped."""
        f = self.substrate.field
        if f.emb is None or not len(f.w):
            return 0
        norms = np.linalg.norm(f.emb, axis=1) > 0
        cos = np.einsum("ij,ij->i", f.emb[f.ei], f.emb[f.ej])
        structural = np.zeros(len(f.w), dtype=bool)
        for w in STRUCTURAL_W:
            structural |= np.abs(f.w0 - w) < 1e-9
        learned = f.w0 == 0
        no_vector = ~norms[f.ei] | ~norms[f.ej]
        similar = cos >= K.EDGE_MIN_COS
        keep = structural | learned | no_vector | similar
        resim = similar & ~structural & ~learned & ~no_vector
        new_w = (cos - K.EDGE_MIN_COS) / (1 - K.EDGE_MIN_COS)
        f.w0 = np.where(resim, new_w, f.w0)
        f.w = np.where(resim, np.minimum(f.w, new_w), f.w)
        dropped = int((~keep).sum())
        f.w = np.where(keep, f.w, 0.0)
        f.prune(1e-9)
        return dropped

    def describe(self) -> dict:
        return {**super().describe(), "v4": self.v4.public(), "v4_switches": self.v4_switches.as_dict()}

    # ---------- the substrate ----------

    def _start_field(self) -> None:
        s = self.substrate
        s.load()
        if s.t is None:
            s.t = minutes(self._cursor())
        f = s.field
        now = at_minute(s.t)
        if f.special("user") is None:
            f.add_node("user", 0, "the user", now=now, embedding=None, similar_edges=False)
        if f.special("self") is None:
            f.add_node("self", 0, "you", now=now, embedding=None, similar_edges=False)
        s.invalidate()
        self._sync()
        s.save()

    def _silence_seconds(self) -> float | None:
        last = self.db.execute("SELECT MAX(ts) FROM messages WHERE role='user'").fetchone()[0]
        if not last:
            return None
        return (self.clock.now() - datetime.fromisoformat(last)).total_seconds()

    def substrate_due_ids(self, positions=None) -> list[int]:
        f = self.substrate.field
        positions = self.substrate.due_nodes if positions is None else positions
        return [f.ref[i] for i in positions if f.kind[i] == "intention"]

    def _node(self, kind: str, ref: int, label: str, vec, *, source: str = "external", valence: float = 0.0,
              arousal: float = 0.0, u: float = 0.0, pe: float = 0.0, self_rel: float = 0.0, a_scale: float = 1.0) -> int:
        """A new node with its salience at creation setting its initial activation and base level (§6.8)."""
        s = self.substrate
        parts = salience_parts(s.field, vec, s.t, valence=valence, arousal=arousal, pe=pe, self_relevance=self_rel)
        sal = salience(parts)
        a0 = (K.A0_BASE + K.A0_GAIN * sal) * (K.OWN_INPUT if source == "own" else 1.0) * a_scale
        i = s.field.add_node(kind, ref, label, now=at_minute(s.t), embedding=vec, source=source, valence=valence,
                             arousal_tag=arousal, u=u, salience=sal, a0=a0, uses=1 + round(sal * K.SALIENT_USES))
        if source != "own" and kind not in ("user", "self"):
            s.novelty = max(s.novelty, parts["novelty"])
            s.drives.pulse("boredom", -K.BOREDOM_NOVELTY_DROP * parts["novelty"])
            s.drives.pulse("arousal", K.AROUSAL_SALIENCE * max(0.0, sal - 0.5))
        s.invalidate()
        return i

    def _sync(self) -> None:
        """New V1 memories, V3 thoughts, intentions and questions become nodes; closed ones leave the field."""
        s = self.substrate
        f = s.field
        vec = lambda blob: np.frombuffer(blob, dtype=np.float32).copy() if blob else None
        user, me = f.special("user"), f.special("self")
        d = s.drives
        self_memories = {r[0] for r in self.db.execute("SELECT memory_id FROM memory_entities WHERE entity_id=?",
                                                        (self.store.self_id,))}
        for r in self.db.execute("SELECT m.*, a.valence AS av, a.arousal AS aa FROM memories m LEFT JOIN memory_affect a "
                                 "ON a.memory_id = m.id WHERE m.valid_to IS NULL ORDER BY m.id").fetchall():
            kind = "episode" if r["kind"] == "episode" else "memory"
            if f.node_for(kind, r["id"]) is not None:
                continue
            i = self._node(kind, r["id"], r["content"], vec(r["embedding"]),
                           valence=r["av"] if r["av"] is not None else d.get("valence"),
                           arousal=r["aa"] if r["aa"] is not None else 0.0,
                           self_rel=1.0 if r["id"] in self_memories else 0.0)
            if kind == "episode" and r["source_session"] is not None:
                f.add_edges([(i, t, K.TRACE_WEIGHT) for (tid,) in self.db.execute(
                    "SELECT id FROM v4_traces WHERE session_id=?", (r["source_session"],))
                    if (t := f.node_for("trace", tid)) is not None])
        for (mid,) in self.db.execute("SELECT id FROM memories WHERE valid_to IS NOT NULL").fetchall():
            for kind in ("memory", "episode"):
                if (i := f.node_for(kind, mid)) is not None and f.alive[i]:
                    f.kill(i)
        links = [(a, b) for a, b, _ in self.db.execute("SELECT src, dst, relation FROM memory_links")]
        edges = []
        for a, b in links:
            ia = f.node_for("memory", a) if f.node_for("memory", a) is not None else f.node_for("episode", a)
            ib = f.node_for("memory", b) if f.node_for("memory", b) is not None else f.node_for("episode", b)
            if ia is not None and ib is not None and f.weight(ia, ib) < K.LINK_WEIGHT:
                edges.append((ia, ib, K.LINK_WEIGHT))
        f.add_edges(edges)
        for r in self.db.execute("SELECT * FROM thoughts ORDER BY id").fetchall():
            kind = "dream" if r["source"] == "dream" else "thought"
            if f.node_for(kind, r["id"]) is None:
                i = self._node(kind, r["id"], r["content"], vec(r["embedding"]), source="own", self_rel=1.0)
                f.add_edges([(i, me, K.OWN_LINK_WEIGHT)])
        for r in self.db.execute("SELECT * FROM intentions_v3 ORDER BY id").fetchall():
            i = f.node_for("intention", r["id"])
            if i is None and r["status"] == "open":
                own = r["source"] != "commitment"
                i = self._node("intention", r["id"], r["content"], vec(r["embedding"]), source="own" if own else
                               "external", u=1.0, self_rel=1.0 if own else 0.0)
                f.add_edges([(i, me if own else user, K.OWN_LINK_WEIGHT if own else K.COMMITMENT_USER_WEIGHT)])
            elif i is not None and r["status"] != "open" and f.alive[i]:
                f.kill(i)
        for r in self.db.execute("SELECT * FROM questions ORDER BY id").fetchall():
            i = f.node_for("question", r["id"])
            if i is None and r["status"] == "open":
                i = self._node("question", r["id"], r["content"], vec(r["embedding"]), source="own", u=1.0, self_rel=1.0)
                f.add_edges([(i, me, K.OWN_LINK_WEIGHT)])
            elif i is not None and r["status"] != "open" and f.alive[i]:
                f.kill(i)
                if r["status"] == "resolved":
                    d.pulse("curiosity", -K.CURIOSITY_RESOLVED)
        self._sync_events()
        s.invalidate()
        s.set_trace_signs({i: sig for tid, sig in self.traces.signals().items()
                           if (i := f.node_for("trace", tid)) is not None})
        self._refresh_threads(self.clock.now())

    def _sync_events(self) -> None:
        """Exchanges become events in the field, chained in order and linked to the facts extracted from them (also
        the backfill of conversations from before episodic memory)."""
        s, f, ep = self.substrate, self.substrate.field, self.episodes
        new = [ep.record(u, r) for u, r in ep.missing()]
        rows = ep.get([e for e in new if e is not None])
        if not rows:
            return
        vecs = None
        if self.store.embed is not None:
            try:
                vecs = np.concatenate([self.store.embed([r["label"] for r in rows[k:k + 64]])
                                       for k in range(0, len(rows), 64)])
            except Exception as e:
                log.warning("event embeddings failed: %s", e)
        for n, r in enumerate(rows):
            i = self._node(r["kind"], r["id"], r["label"] + (f" — word for word: “{r['verbatim']}”" if r["verbatim"]
                                                               else ""),
                           vecs[n] if vecs is not None else None, valence=r["valence"], arousal=r["arousal"],
                           a_scale=0.5 if len(rows) > 1 else 1.0)   # a backfill doesn't light everything at once
            prev = self.db.execute("SELECT id, session_id FROM v4_events WHERE seq < ? ORDER BY seq DESC LIMIT 1",
                                   (r["seq"],)).fetchone()
            if prev and (j := f.node_for(self.db.execute("SELECT kind FROM v4_events WHERE id=?", (prev["id"],))
                                         .fetchone()[0], prev["id"])) is not None:
                f.add_edges([(i, j, K.EVENT_CHAIN_W if prev["session_id"] == r["session_id"] else K.EVENT_CHAIN_W / 2)])
            nxt = self.db.execute("SELECT MIN(ts) FROM messages WHERE role='user' AND session_id=? AND id > ?",
                                  (r["session_id"], r["message_id"])).fetchone()[0]
            facts = self.db.execute("SELECT id, kind FROM memories WHERE source_session=? AND created_at >= ?"
                                    + (" AND created_at < ?" if nxt else ""),
                                    (r["session_id"], r["at"], *([nxt] if nxt else []))).fetchall()
            f.add_edges([(i, k, K.EVENT_FACT_W) for m in facts
                         if (k := f.node_for("episode" if m["kind"] == "episode" else "memory", m["id"])) is not None])
            if (before := self.db.execute("SELECT id FROM v4_events WHERE seq=?", (r["seq"] - 1,)).fetchone()):
                ep.revisit(before[0])   # the next exchange is the aftermath of the one before
        s.invalidate()

    def _refresh_threads(self, now: datetime) -> None:
        """Proximity to due for open intentions (goal tension), due intentions not yet acted on, unanswered messages."""
        s, f = self.substrate, self.substrate.field
        today = now.date()
        prox = {}
        for it in self.later.open() if self._later_on() else []:
            if (i := f.node_for("intention", it.id)) is None:
                continue
            if now < datetime.fromisoformat(it.not_before):
                prox[i] = 0.0
            elif it.due:
                days = (date.fromisoformat(it.due) - today).days
                prox[i] = 1.0 if days <= 0 else 0.5 if days == 1 else 0.2 if days <= 7 else 0.1
            else:
                prox[i] = 0.1
        s.proximity = prox
        acted = self._due_acted(now)
        s.due_nodes = [i for it in (self.later.due(now) if self._later_on() else [])
                       if it.id not in acted and (i := f.node_for("intention", it.id)) is not None]
        last = self.db.execute("SELECT message_id, at FROM outbox ORDER BY message_id DESC LIMIT 1").fetchone()
        s.unanswered = bool(last) and not self.db.execute("SELECT 1 FROM messages WHERE role='user' AND id > ?",
                                                          (last[0],)).fetchone() and \
            now - datetime.fromisoformat(last[1]) >= timedelta(hours=K.FRUSTRATION_UNANSWERED_H)
        self._last_hour = int((s.t or 0) // 60)

    # ---------- turns ----------

    def _in_conversation(self) -> bool:
        """Messages are flowing: the last one is less than 30 sim minutes old (the gate stays closed)."""
        if self.session is None:
            return False
        last = self.store.last_message(self.session.id)
        return last is not None and self.substrate.t - minutes(datetime.fromisoformat(last["ts"])) \
            < K.CONVERSATION_IDLE_MIN

    def _catch_up(self, now: datetime) -> None:
        """Step the field quietly up to now (a conversation's turns; time not lived through advance())."""
        s = self.substrate
        dt = self.v4.dt_min
        while s.t + dt <= minutes(now) + 1e-9:
            s.step(dt, conversation=self._in_conversation(), quiet=True)

    def _prepare_turn(self, text: str, now: datetime) -> dict:
        """The message arrives: its input reaches similar nodes and the user node; what the reply will see is read
        off the field after that input has spread for 3 sim minutes (without touching the state)."""
        s, f = self.substrate, self.substrate.field
        qv = self.store.embed_one(text)
        p = s.params("conversation")
        sims = f.similarities(qv)
        kick = np.zeros(len(f))
        other = np.where(f.mask("memory", "episode"), 0.0, sims)
        near = [int(i) for i in np.argsort(-other)[:K.MSG_TOP] if other[i] >= K.EDGE_MIN_COS]
        if near:
            best_sim = other[near[0]]
            for i in near:
                kick[i] = K.MSG_KICK * (other[i] - K.EDGE_MIN_COS + 0.05) / (best_sim - K.EDGE_MIN_COS + 0.05) \
                    * p["input"]
        # V1 memories are reached through every channel of V1's search: meaning, words, names, dates, links
        found = search(self.store, text, now=now, date_range=parse_time_range(text, now.date()), limit=K.QUERY_TOP,
                       min_score=0.0)
        best = max((c.score for c in found.hits), default=0.0)
        for c in found.hits:
            if best > 0 and (i := f.node_for("episode" if c.memory.kind == "episode" else "memory",
                                             c.memory.id)) is not None:
                kick[i] = K.QUERY_KICK * c.score / best * p["input"]
        # what the conversation is about, not only the last line ("a happy end anyway" after talking about the
        # finale): the last few messages reach memory too, more weakly (entry 10)
        if self.session is not None and not self._gap_exceeded(self.session.id):
            recent = self.db.execute("SELECT content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                                     (self.session.id, K.TOPIC_MESSAGES)).fetchall()
            topic = "\n".join(r[0][:K.TOPIC_CHARS] for r in reversed(recent))
            if topic.strip():
                around = search(self.store, topic, now=now, limit=K.QUERY_TOP, min_score=0.0)
                top = max((c.score for c in around.hits), default=0.0)
                for c in around.hits:
                    if top > 0 and (i := f.node_for("episode" if c.memory.kind == "episode" else "memory",
                                                    c.memory.id)) is not None:
                        kick[i] = max(kick[i], K.TOPIC_WEIGHT * K.QUERY_KICK * c.score / top * p["input"])
        if (user := f.special("user")) is not None:
            kick[user] += K.USER_KICK
        for i in s.due_nodes:
            kick[i] += K.DUE_KICK
        # episodic memory: "yesterday" reaches yesterday's events; "where did we stop?" the end of the last talk
        if (span := parse_time_range(text, now.date())) is not None:
            lo, hi = span[0].isoformat(), span[1].isoformat() + "T99"
            for (eid, kind) in self.db.execute("SELECT id, kind FROM v4_events WHERE at BETWEEN ? AND ?", (lo, hi)):
                if (i := f.node_for(kind, eid)) is not None:
                    kick[i] += K.EVENT_TIME_KICK
        if RECENT.search(text):
            for (eid, kind) in self.db.execute("SELECT id, kind FROM v4_events ORDER BY seq DESC LIMIT ?",
                                               (K.EVENTS_LAST,)):
                if (i := f.node_for(kind, eid)) is not None:
                    kick[i] += K.EVENT_TIME_KICK
        f.kick(kick, s.t)
        s.present_until = s.t + K.PRESENCE_MIN   # someone is here
        novelty = 1.0 - float(max(0.0, sims.max())) if len(sims) and qv is not None else 1.0
        s.novelty = max(s.novelty, novelty)
        s.drives.pulse("arousal", K.AROUSAL_MESSAGE * (1 - s.drives.get("arousal")))
        s.drives.pulse("boredom", -K.BOREDOM_NOVELTY_DROP * novelty)
        s._masks()
        conflict, nodes = s.conflict()
        preview = f.preview(s.t, K.RECALL_PREVIEW_MIN, self.v4.dt_min, p, s.drive_input(nodes),
                            s.attention.outside_focus(f))
        turn = {"preview": preview, "wm": s.attention.working_memory(f, preview), "recall": None,
                "trace_ids": [], "trace_act": []}
        if self.v4_switches.on("grip"):
            earlier = 0
            if self.session is not None and not self._gap_exceeded(self.session.id):
                earlier = self.store.message_count(self.session.id)
            turn["grip"] = g = assess(text, store=self.store, field_=f, qv=qv, session=self.session,
                                      previous_turns=earlier, preview=preview)
            s.drives.pulse("uncertainty", K.GRIP_UNCERTAINTY * (1 - g.value))
        early = self.session is None or self._gap_exceeded(self.session.id) or \
            self.store.message_count(self.session.id) < 4
        turn["event_ids"] = self.episodes.select(preview, text, early,
                                                 self.session.id if self.session is not None and early is False
                                                 else None)
        if self.v4_switches.on("recall"):
            turn["recall"] = recall(self.store, f, preview, exclude_episodes=self._ablated("episodic"))
        if self.v4_switches.on("traces") and not self._ablated("traces"):
            idx = np.flatnonzero(f.mask("trace"))
            order = sorted(idx, key=lambda i: -preview[i])[:K.TRACES_SHOWN]
            order = [i for i in order if preview[i] > 0.01]
            turn["trace_ids"] = [f.ref[i] for i in order]
            turn["trace_act"] = [round(float(preview[i]), 4) for i in order]
        return turn

    def reply(self, text: str) -> str:
        if not self.field_on:
            return super().reply(text)
        self.worker.drain()
        now = self.clock.now()
        self._catch_up(now)
        if self.v4_switches.on("sleep_mode") and self.substrate.sleep.mode != "awake":
            self._handle(self.substrate.wake("message"), [])   # a user message always wakes the agent (D10)
        self._turn = self._prepare_turn(text, now)
        answer = super().reply(text)
        self._record_turn()
        return answer

    def _record_turn(self) -> None:
        s, f = self.substrate, self.substrate.field
        reply_id = self.session.buffer[-1]["id"]
        shown = self.context.shown
        recalled = [h.memory.id for h in (self._turn["recall"].hits if self._turn.get("recall") else []) if h.in_prompt]
        trace_ids = shown.get("trace_ids", [])
        acts = dict(zip(self._turn.get("trace_ids", []), self._turn.get("trace_act", [])))
        grip = self._turn.get("grip")
        row = (reply_id, json.dumps(trace_ids), json.dumps([acts.get(t, 0.0) for t in trace_ids]),
               json.dumps(shown.get("wm", [])), json.dumps(recalled),
               json.dumps({k: round(v, 3) for k, v in s.drives.x.items()}),
               json.dumps(grip.issues if grip else [], ensure_ascii=False))
        t = s.t
        positions = [i for i in (f.node_for("memory", m) or f.node_for("episode", m) for m in recalled) if i is not None]
        positions += [i for tid in trace_ids if (i := f.node_for("trace", tid)) is not None]
        positions += [f.index[n] for n in shown.get("wm", []) if n in f.index]

        def write():
            self.db.execute("INSERT OR REPLACE INTO v4_turn_state(message_id, trace_ids, trace_activations, wm, recall, "
                            "drives, grip) VALUES (?, ?, ?, ?, ?, ?, ?)", row)
            for i in set(positions):   # being recalled is a use: rehearsal (§6.8)
                f.use(i, t)
                f.last_considered[i] = t
            if self.v4_switches.on("reconsolidation"):
                reconsolidate(f, [i for i in positions if f.kind[i] in ("memory", "episode")], s.drives.get("mood"))
        self.worker.submit(write)

    def _after_turn(self, session: Session) -> None:
        if not self.field_on:
            super()._after_turn(session)
            return
        s = self.substrate
        AgentV1._after_turn(self, session)   # V1: extraction, fold
        lessons = self.switches.lessons and not self.v4_switches.on("traces")
        v2_intentions = self.switches.intentions and not self._later_on()
        if lessons or v2_intentions:
            self.observer.observe(session, lessons=lessons, intentions=v2_intentions)
            if lessons and len(self.lessons.unreflected()) >= self.v2.reflect_every:
                self.reflector.reflect(session_summary=session.summary)
        reaction = None
        if self.v4_switches.on("traces"):
            reaction = self.turn_observer_v4.observe_all(session, affect=self.v3_switches.affect,
                                                         intentions=self._later_on())
        else:
            self.turn_observer.observe(session, affect=self.v3_switches.affect, intentions=self._later_on())
        if not self.v4_switches.on("gate") and self.v3_switches.stream:
            self.stream.tick(rhythm.CONVERSATION)
        if self.v3_switches.affect:
            now = self.clock.now()
            cur = self.affect.current(now)
            s.drives.appraisal(cur.valence, self.affect.mood(now).valence, cur.arousal)
        self._sync()
        if reaction is not None:
            self._trace(reaction)
        s.save()

    def _trace(self, r: dict) -> None:
        """A reaction to the previous reply: prediction error, and an episode if it says anything (§6.7, §6.8)."""
        s, f, d = self.substrate, self.substrate.field, self.substrate.drives
        state = self.db.execute("SELECT trace_ids, trace_activations FROM v4_turn_state WHERE message_id=?",
                                (r["reply"]["id"],)).fetchone()
        ids, acts = (json.loads(state[0]), json.loads(state[1])) if state else ([], [])
        signals = self.traces.signals()
        pairs = [(signals[t], a) for t, a in zip(ids, acts) if t in signals]
        expected = expected_signal([p[0] for p in pairs], [p[1] for p in pairs])
        pe = r["signal"] - expected
        d.pulse("arousal", K.PE_AROUSAL * abs(pe))
        d.pulse("curiosity", K.PE_CURIOSITY * abs(pe))
        d.pulse("frustration", K.PE_FRUSTRATION * max(0.0, -pe) - K.PRAISE_RELIEF * max(0.0, r["signal"]))
        s.engagement = max(0.0, r["signal"])
        detail = {"reply": r["reply"]["id"], "signal": r["signal"], "expected": round(expected, 4), "pe": round(pe, 4),
                  "from_traces": ids}
        if abs(r["signal"]) < K.TRACE_MIN_SIGNAL and abs(pe) < K.TRACE_MIN_PE:
            s.log("INSERT INTO v4_learning(at, event, detail) VALUES (?, 'pe', ?)",
                  (self.store.now(), json.dumps({**detail, "trace": None})))
            return
        situation, reaction = r["situation"]["content"], r["reaction"]["content"]
        vec = self.store.embed_one(f"{situation}\n{reaction}")
        parts = salience_parts(f, vec, s.t, valence=r["signal"], arousal=min(1.0, abs(pe)), pe=pe)
        sal = salience(parts)
        trace_id, label = self.traces.add(r, expected=expected, pe=pe, salience=sal,
                                           call_id=last_call_id(self.db, "observe_v4"), vec=vec)
        i = self._node("trace", trace_id, label, vec, valence=r["signal"], arousal=min(1.0, abs(pe)), pe=pe)
        mine = (f.ei == i) | (f.ej == i)
        f.w[mine] = np.minimum(1.0, f.w[mine] * (1 + K.PE_EDGE_GAIN * abs(pe)))   # a surprise teaches more
        f.add_edges([(i, f.special("user"), K.TRACE_WEIGHT)])
        if (ep := self.db.execute("SELECT id FROM memories WHERE kind='episode' AND source_session=? AND valid_to IS NULL",
                                  (r["session_id"],)).fetchone()) and (j := f.node_for("episode", ep[0])) is not None:
            f.add_edges([(i, j, K.TRACE_WEIGHT)])
        s.set_trace_signs({i: r["signal"]})
        # the aftermath of a passage: the user's reaction can make it a charged one, kept word for word
        for (eid,) in self.db.execute("SELECT id FROM v4_events WHERE reply_id=?", (r["reply"]["id"],)).fetchall():
            self.episodes.revisit(eid)
        s.log("INSERT INTO v4_learning(at, event, detail) VALUES (?, 'pe', ?)",
              (self.store.now(), json.dumps({**detail, "trace": trace_id, "salience": round(sal, 3)})))

    # ---------- sessions ----------

    def _finalize(self, session_id: int) -> None:
        if not getattr(self, "_v4_ready", False):
            self._pending_finalize.append(session_id)
            return
        if not self.v4_switches.field:
            super()._finalize(session_id)
            return
        AgentV1._finalize(self, session_id)
        for name in V2_NAMES:
            if not getattr(self.switches, name):
                continue
            if (name == "lessons" and self.v4_switches.on("traces")) or \
                    (name == "selfmodel" and self.v4_switches.on("narrative")):
                continue   # no reflector without lessons; the narrative is written in sleep
            if hasattr(m := self._mechanisms[name], "after_session"):
                m.after_session(session_id)
        self._sync()
        self.substrate.save()

    # ---------- time ----------

    def advance(self, to: datetime) -> list[dict]:
        """Live through time up to `to`, step by step. Returns the messages the agent wrote first, in order."""
        if not self.field_on:
            return super().advance(to)
        self.worker.drain()
        s = self.substrate
        dt = self.v4.dt_min
        written: list[dict] = []
        end = minutes(to)
        while s.t + dt <= end + 1e-9:
            close = self._session_close_at()
            if close is not None and minutes(close) <= s.t + 1e-9:
                self._set_time(close)
                self.end_session()
                self._log_event(close, "session_close", True)
                continue
            if self.session is None:
                self._v3_events(written)
            if int(s.t // 60) != self._last_hour:
                self._refresh_threads(at_minute(s.t))
            for ev in s.step(dt, conversation=self._in_conversation()):
                self._handle(ev, written)
        s.save()
        set_meta(self.db, "v3_cursor", iso(at_minute(s.t)))
        return written

    def _v3_events(self, written: list[dict]) -> None:
        """V3's stream and monitor when the gate is off; V3's nightly sleep when sleep_mode is off (ablations)."""
        s, v3s = self.substrate, self.v3_switches
        now = at_minute(s.t)
        if not self.v4_switches.on("gate") and (v3s.stream or v3s.wakes):
            nxt = get_meta(self.db, NEXT_STREAM)
            if nxt is None or datetime.fromisoformat(nxt) <= now:
                if nxt is not None:
                    self._set_time(now)
                    self._stream_tick(now, written)
                m = rhythm.mode(now, self.v3, False)
                set_meta(self.db, NEXT_STREAM, iso(now + rhythm.stream_period(m, self.v3)))
        if not self.v4_switches.on("sleep_mode") and v3s.sleep:
            nxt = get_meta(self.db, NEXT_SLEEP)
            if nxt is None:
                set_meta(self.db, NEXT_SLEEP, iso(rhythm.next_sleep(now, self.v3)))
            elif datetime.fromisoformat(nxt) <= now:
                self._set_time(now)
                self._run_event("sleep", now, written)
                if self.v4_switches.on("narrative"):
                    s.drives.set("dissonance", max(s.drives.get("dissonance"), self.narrator.check(now)))
                set_meta(self.db, NEXT_SLEEP, iso(rhythm.next_sleep(now, self.v3)))
                self._sync()

    def _handle(self, ev: Event, written: list[dict]) -> None:
        s = self.substrate
        at = at_minute(ev.t)
        if ev.kind == "fire":
            self._fire(ev, written)
        elif ev.kind == "dream":
            self._dream(ev)
        elif ev.kind == "onset":
            pooled = s.pool()
            s.log("INSERT INTO v4_learning(at, event, detail) VALUES (?, 'edges', ?)",
                  (iso(at), json.dumps(s.prune_and_count())))
            set_meta(self.db, DREAMS_KEY, "[]")
            s.log("INSERT INTO v4_sleep(at, event, detail) VALUES (?, 'onset', ?)",
                  (iso(at), json.dumps({**ev.detail, "pooled": pooled})))
        elif ev.kind in ("nrem", "rem"):
            s.log("INSERT INTO v4_sleep(at, event, detail) VALUES (?, ?, ?)", (iso(at), ev.kind, json.dumps(ev.detail)))
        elif ev.kind == "narrative":
            self._set_time(at)
            self._night_review(at)
        elif ev.kind == "wake":
            woke_up = s.burst()   # waking is a burst, not a slow start
            dreams = json.loads(get_meta(self.db, DREAMS_KEY) or "[]")
            f = s.field
            on_mind = [f.label[i][:160] for i in s.attention.working_memory(f) if f.kind[i] not in ("user", "self")][:3]
            set_meta(self.db, WOKE_KEY, json.dumps({"at": iso(at), "slept_hours": ev.detail.get("slept_hours"),
                                                    "absent_hours": ev.detail.get("absent_hours"),
                                                    "dreams": dreams, "on_mind": on_mind}, ensure_ascii=False))
            s.log("INSERT INTO v4_sleep(at, event, detail) VALUES (?, 'wake', ?)",
                  (iso(at), json.dumps({**ev.detail, "burst": woke_up, "on_mind": on_mind}, ensure_ascii=False)))

    def _night_review(self, at: datetime) -> None:
        """End of the first NREM: the narrative review and the dissonance check (or V3's sleep steps, as ablations)."""
        s = self.substrate
        since = iso(at - timedelta(days=1)) if s.sleep.last_wake is None else \
            iso(min(at_minute(s.sleep.last_wake), at - timedelta(hours=1)))
        detail = {}
        if self.switches.lessons and not self.v4_switches.on("traces"):
            detail["lessons"] = self.sleeper._lessons(at)
        if self.switches.selfmodel:
            if self.v4_switches.on("narrative"):
                detail["narrative_changed"] = self.narrator.review(at, since)
                value = self.narrator.check(at)
                s.drives.set("dissonance", max(s.drives.get("dissonance"), value))
                detail["dissonance"] = round(value, 4)
            else:
                detail["portrait_changed"] = self.sleeper._portrait(at, since)
        s.log("INSERT INTO v4_sleep(at, event, detail) VALUES (?, 'narrative', ?)", (iso(at), json.dumps(detail)))
        self._sync()

    def _fire(self, ev: Event, written: list[dict]) -> None:
        """The gate fired: the wake model interprets the coalition; the selector decides what happens (§6.6)."""
        s, f = self.substrate, self.substrate.field
        at = at_minute(ev.t)
        self._set_time(at)
        r = ev.reading
        wake_id = self.db.execute("INSERT INTO wakes(at, trigger) VALUES (?, ?)",
                                  (iso(at), json.dumps({"sources": r.sources, "cause": ev.cause,
                                                        "coalition": [int(f.ids[i]) for i in ev.coalition]}))).lastrowid
        data, call_id = self.verbalizer.verbalize(ev)
        changed, msgs, decisions = self.actions.apply(data, ev, wake_id)
        written.extend(msgs)
        thought = str(data.get("thought") or "").strip()
        if thought:
            self._own_node(thought, "wake", wake_id, ev.coalition)
        if self.v3_switches.affect and isinstance(data.get("feeling"), dict):
            fl = data["feeling"]
            self.affect.update(clamp(fl.get("valence"), fl.get("arousal"), {}), cause=f"own thought: {thought[:100]}",
                               weight=THOUGHT_WEIGHT)
            cur = self.affect.current(at)
            s.drives.appraisal(cur.valence, self.affect.mood(at).valence, cur.arousal)
        due_ids = self.substrate_due_ids(ev.due)
        blocked_write = any(d.get("type") == "write" and not d.get("applied") for d in decisions)
        if due_ids and not blocked_write:   # considered; if it wanted to speak and couldn't, it comes back later
            acted = self._due_acted(at)
            set_meta(self.db, DUE_ACTED, json.dumps({"day": at.date().isoformat(), "ids": sorted(acted | set(due_ids))}))
        for i in ev.coalition:
            f.last_considered[i] = ev.t
        self.thoughts.considered([f.ref[i] for i in ev.coalition if f.kind[i] == "question"], at)
        s.after_fire(ev)
        self.db.execute("UPDATE wakes SET thought=?, decisions=?, productive=?, llm_call_id=? WHERE id=?",
                        (thought, json.dumps(decisions, ensure_ascii=False), int(changed), call_id, wake_id))
        s.log("INSERT INTO v4_firings(at, kind, coherence, urgency, brake, sources, coalition, cause, grew_hours, "
              "wake_id, thought, decisions, llm_call_id) VALUES (?, 'fire', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (iso(at), r.coherence, r.urgency, r.brake, json.dumps(r.sources),
               json.dumps([int(f.ids[i]) for i in ev.coalition]), ev.cause, ev.grew_hours, wake_id, thought,
               json.dumps(decisions, ensure_ascii=False), call_id))
        self._log_event(at, "wake", True, json.dumps({"cause": ev.cause, **{k: round(v, 3) for k, v in r.sources.items()}}))
        self._sync()
        s.save()
        log.info("firing (%s) at %s: %s", ev.cause, iso(at), thought[:200])

    def _dream(self, ev: Event) -> None:
        s, f = self.substrate, self.substrate.field
        at = at_minute(ev.t)
        self._set_time(at)
        data, call_id = self.verbalizer.verbalize(ev, dream=True)   # proposals, if any, are dropped
        text = str(data.get("thought") or "").strip()
        if text:
            self._own_node(text, "dream", None, ev.coalition)
            dreams = json.loads(get_meta(self.db, DREAMS_KEY) or "[]")
            set_meta(self.db, DREAMS_KEY, json.dumps(dreams + [text], ensure_ascii=False))
        s.after_fire(ev)
        r = ev.reading
        s.log("INSERT INTO v4_firings(at, kind, coherence, urgency, brake, sources, coalition, cause, grew_hours, "
              "thought, llm_call_id) VALUES (?, 'dream', ?, ?, ?, ?, ?, 'dream', ?, ?, ?)",
              (iso(at), r.coherence, r.urgency, r.brake, json.dumps(r.sources),
               json.dumps([int(f.ids[i]) for i in ev.coalition]), ev.grew_hours, text, call_id))
        s.log("INSERT INTO v4_sleep(at, event, detail) VALUES (?, 'dream', ?)",
              (iso(at), json.dumps({"text": text}, ensure_ascii=False)))
        s.save()

    def _own_node(self, text: str, source: str, source_id: int | None, coalition: list[int]) -> None:
        """A thought becomes a node at weight 0.3, linked to the coalition it came from (it excites it, T55)."""
        f, s = self.substrate.field, self.substrate
        vec = self.store.embed_one(text)
        if vec is not None and source != "dream":   # habituation: a near-repeat refreshes the old thought (entry 11)
            sims = f.similarities(vec)
            recent = f.mask("thought") & ((s.t - f.created) <= K.REPEAT_THOUGHT_HOURS * 60)
            if recent.any() and float(sims[recent].max()) >= K.REPEAT_THOUGHT_COS:
                i = int(np.argmax(np.where(recent, sims, -1.0)))
                f.use(i, s.t)
                f.add_edges([(i, j, K.THOUGHT_WEIGHT) for j in coalition])
                return
        tid = self.thoughts.add(text, source=source, source_id=source_id)
        if tid is None:
            return
        vec = self.db.execute("SELECT embedding FROM thoughts WHERE id=?", (tid,)).fetchone()[0]
        i = self._node("dream" if source == "dream" else "thought", tid, text,
                       np.frombuffer(vec, dtype=np.float32).copy() if vec else None, source="own", self_rel=1.0)
        f.add_edges([(i, j, K.THOUGHT_WEIGHT) for j in coalition] + [(i, f.special("self"), K.OWN_LINK_WEIGHT)])

    # ---------- the chat: coming to, presence ----------

    def come_to(self, now: datetime) -> list[dict]:
        """The program starts. If it was off longer than ABSENCE_MIN, that time was absence: no thoughts, no messages
        (nothing could be read then); it is lived quietly as sleep, then the agent wakes with a burst. A shorter gap
        is lived as usual. Returns messages written first (only from the usual case)."""
        if not self.field_on:
            return self.advance(now)
        s = self.substrate
        gap = minutes(now) - s.t
        if gap <= K.ABSENCE_MIN:
            return self.advance(now)
        if self.session is not None and self._gap_exceeded(self.session.id):
            self._set_time(now)
            self.end_session()
        if self.v4_switches.on("sleep_mode") and s.sleep.mode == "awake":
            s.sleep.fall_asleep(s.field, s.t, s.rng)
        while s.t + 1.0 <= minutes(now) + 1e-9:
            s.step(1.0, conversation=False, quiet=True)
        s.sleep.mode = "awake"
        ev = Event("wake", s.t, detail={"reason": "start", "absent_hours": round(gap / 60, 2),
                                         "slept_hours": round(gap / 60, 2)})
        s.sleep.wake(s.t)
        self._set_time(at_minute(s.t))
        self._handle(ev, [])
        s.save()
        return []

    def presence(self) -> None:
        """The user opened the chat: they are here before saying anything (input to the user node; speaking first
        is easier while they are)."""
        if not self.field_on:
            return
        s = self.substrate
        s.presence()
        s.log("INSERT INTO v4_attention(at, event, focus, energy, coalition) VALUES (?, 'presence', ?, ?, '[]')",
              (iso(at_minute(s.t)), s.attention.focus, 0.0))
        s.save()

    # ---------- harness ----------

    def snapshot(self, path) -> None:
        if self.field_on:
            self.worker.drain()
            self.substrate.save()
        super().snapshot(path)

    def close(self) -> None:
        if getattr(self, "_v4_ready", False) and self.v4_switches.field:
            self.worker.drain()
            self.substrate.save()
        super().close()

    def state_summary(self) -> dict:
        out = super().state_summary()
        if not self.v4_switches.field:
            return out
        s = self.substrate
        q = lambda sql: self.db.execute(sql).fetchone()[0]
        kinds = {r[0]: r[1] for r in self.db.execute("SELECT kind, COUNT(*) FROM v4_firings GROUP BY kind")}
        causes = {r[0]: r[1] for r in self.db.execute("SELECT cause, COUNT(*) FROM v4_firings WHERE kind='fire' "
                                                      "GROUP BY cause")}
        spontaneous = [r[0] for r in self.db.execute("SELECT grew_hours FROM v4_firings WHERE kind='fire' AND "
                                                     "cause='spontaneous'")]
        out["v4"] = {
            **s.field.stats(),
            "firings": kinds.get("fire", 0), "dreams": kinds.get("dream", 0),
            "near_misses": {"yawn": kinds.get("yawn", 0), "worry": kinds.get("worry", 0)},
            "causes": causes, "spontaneous_grew_hours": spontaneous,
            "sleeps": q("SELECT COUNT(*) FROM v4_sleep WHERE event='onset'"),
            "wakes": {r[0]: r[1] for r in self.db.execute(
                "SELECT json_extract(detail, '$.reason'), COUNT(*) FROM v4_sleep WHERE event='wake' GROUP BY 1")},
            "traces": q("SELECT COUNT(*) FROM v4_traces"),
            "mean_abs_pe": q("SELECT AVG(ABS(json_extract(detail, '$.pe'))) FROM v4_learning WHERE event='pe'"),
            "dissonance_checks": q("SELECT COUNT(*) FROM v4_dissonance"),
            "attention_switches": q("SELECT COUNT(*) FROM v4_attention WHERE event='switch'"),
            "intrusions": q("SELECT COUNT(*) FROM v4_attention WHERE event='intrusion'"),
            "drives": {k: round(v, 3) for k, v in s.drives.x.items()},
        }
        return out
