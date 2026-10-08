"""Scenario format: scripted sessions on a simulated timeline plus probes run on forks of the state."""

import operator
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from ..common.clock import parse_offset
from .scoring import MEASURES, measures

TURN_GAP = timedelta(minutes=2)  # default simulated time between turns
# Filler sessions land on whole days (same time of day as the scenario start) and keep this far from key
# sessions and each other, so each stays a separate conversation; a collision moves to the next day
FILLER_MARGIN = timedelta(hours=4)


_OPS = {"<=": operator.le, ">=": operator.ge, "==": operator.eq, "!=": operator.ne, "<": operator.lt,
        ">": operator.gt}
_CLAUSE = re.compile(r"^\s*(\w+)\s*(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass
class Condition:
    """`bullets > 0 and words >= 200`: clauses over measures() of the agent's previous reply, joined by `and`."""
    text: str
    clauses: list[tuple[str, str, float]]

    @classmethod
    def parse(cls, text: str) -> "Condition":
        clauses = []
        for part in re.split(r"\s+and\s+", str(text).strip()):
            m = _CLAUSE.match(part)
            if not m:
                raise ValueError(f"bad condition {text!r}: expected '<measure> <op> <number> [and ...]'")
            if m.group(1) not in MEASURES:
                raise ValueError(f"bad condition {text!r}: unknown measure {m.group(1)!r}; "
                                 f"choose from {', '.join(MEASURES)}")
            clauses.append((m.group(1), m.group(2), float(m.group(3))))
        return cls(str(text), clauses)

    def holds(self, m: dict[str, float]) -> bool:
        return all(_OPS[op](m[name], value) for name, op, value in self.clauses)


@dataclass
class Turn:
    user: str                      # the text; for a contingent turn, the `else` branch
    wait: timedelta | None = None  # extra simulated time before this turn
    branches: list[tuple[Condition, str]] = field(default_factory=list)  # contingent turn: first match wins

    def choose(self, previous_reply: str | None) -> tuple[str, int | None]:
        """The user's message given the agent's previous reply, and the index of the branch taken
        (len(branches) for `else`, None for a plain turn). Deterministic: the same reply gives the same text."""
        if not self.branches:
            return self.user, None
        if previous_reply is None:
            raise ValueError("a contingent turn needs a previous reply from the agent")
        m = measures(previous_reply)
        for i, (cond, text) in enumerate(self.branches):
            if cond.holds(m):
                return text, i
        return self.user, len(self.branches)


@dataclass
class SessionSpec:
    at: timedelta
    turns: list[Turn]
    new_session: bool = False  # force a boundary even if the silence is shorter than the session gap
    filler: str | None = None  # topic, if drawn from a filler bank


@dataclass
class Probe:
    id: str
    at: timedelta
    ask: str
    new_session: bool = True
    expect: dict = field(default_factory=dict)
    judge: dict[str, str] = field(default_factory=dict)   # rubric name -> rubric
    gold_memories: list[str] = field(default_factory=list)
    measure: str | None = None                            # E4: behavioral measure compared against B0
    tags: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    id: str
    lang: str
    start: datetime
    sessions: list[SessionSpec]
    probes: list[Probe]
    experiment: str = ""
    description: str = ""
    path: Path | None = None


def _turn(raw) -> Turn:
    if isinstance(raw, str):
        return Turn(raw)
    wait = parse_offset(raw["wait"]) if raw.get("wait") is not None else None
    if "user_if" not in raw:
        return Turn(str(raw["user"]), wait)
    branches, default = [], None
    for item in raw["user_if"]:
        if "else" in item:
            default = str(item["else"])
        else:
            branches.append((Condition.parse(item["when"]), str(item["user"])))
    if not branches or default is None:
        raise ValueError(f"user_if needs at least one `when` branch and an `else`: {raw!r}")
    return Turn(default, wait, branches)


def _judge(raw) -> dict[str, str]:
    if not raw:
        return {}
    if isinstance(raw, str):
        return {"judge": raw}
    return {str(k): str(v) for k, v in raw.items()}


def _find_bank(path: Path, bank: str) -> Path:
    for parent in path.resolve().parents:
        candidate = parent / "filler" / f"{bank}.yaml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"{path}: filler bank '{bank}' not found (looked for filler/{bank}.yaml upwards)")


def filler_sessions(spec: dict, path: Path, taken: list[timedelta]) -> list[SessionSpec]:
    """Background conversations drawn from a shared bank, spread evenly over a window, deterministic by seed.
    They add realistic distance between key sessions and distractors for retrieval."""
    bank = yaml.safe_load(_find_bank(path, spec.get("bank", "en")).read_text(encoding="utf-8"))["sessions"]
    count = int(spec["sessions"])
    if count > len(bank):
        raise ValueError(f"{path}: asked for {count} filler sessions, bank has {len(bank)}")
    chosen = random.Random(spec.get("seed", 0)).sample(bank, count)
    lo, hi = (parse_offset(x) for x in spec["between"])
    step = (hi - lo) / max(count - 1, 1)
    if count > 1 and step < timedelta(days=1):
        raise ValueError(f"{path}: filler window too narrow for {count} sessions (need at least a day each)")
    out, occupied = [], list(taken)
    for i, item in enumerate(chosen):
        at = timedelta(days=round((lo + step * i) / timedelta(days=1)))
        while any(abs(at - t) < FILLER_MARGIN for t in occupied):
            at += timedelta(days=1)
        occupied.append(at)
        out.append(SessionSpec(at, [_turn(t) for t in item["turns"]], filler=str(item.get("topic", f"filler{i}"))))
    return out


def load_scenario(path: Path | str) -> Scenario:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    start = data["start"]
    start = start if isinstance(start, datetime) else datetime.fromisoformat(str(start))
    sessions = [SessionSpec(parse_offset(s.get("at", 0)), [_turn(t) for t in s["turns"]],
                            bool(s.get("new_session", False))) for s in data.get("sessions", [])]
    if data.get("filler"):
        sessions += filler_sessions(data["filler"], path, [s.at for s in sessions])
    probes = []
    for i, p in enumerate(data.get("probes", []), 1):
        probes.append(Probe(
            id=str(p.get("id") or f"p{i}"), at=parse_offset(p["at"]), ask=str(p["ask"]),
            new_session=bool(p.get("new_session", True)), expect=dict(p.get("expect") or {}),
            judge=_judge(p.get("judge")), gold_memories=[str(g) for g in p.get("gold_memories") or []],
            measure=p.get("measure"), tags=list(p.get("tags") or [])))
    sessions.sort(key=lambda s: s.at)
    if sessions and sessions[0].turns and sessions[0].turns[0].branches:
        raise ValueError(f"{path}: the first turn can't be contingent (there is no previous reply)")
    ids = [p.id for p in probes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: duplicate probe ids")
    experiment = data.get("experiment") or (path.parent.name if path.parent.name.startswith("e") else "")
    return Scenario(id=str(data.get("id") or path.stem), lang=str(data.get("lang", "en")), start=start,
                    sessions=sessions, probes=sorted(probes, key=lambda p: p.at),
                    experiment=experiment, description=str(data.get("description", "")), path=path)
