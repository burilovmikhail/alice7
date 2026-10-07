"""Scenario format: scripted sessions on a simulated timeline plus probes run on forks of the state."""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from ..common.clock import parse_offset

TURN_GAP = timedelta(minutes=2)  # default simulated time between turns
# Filler sessions land on whole days (same time of day as the scenario start) and keep this far from key
# sessions and each other, so each stays a separate conversation; a collision moves to the next day
FILLER_MARGIN = timedelta(hours=4)


@dataclass
class Turn:
    user: str
    wait: timedelta | None = None  # extra simulated time before this turn


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
    return Turn(str(raw["user"]), parse_offset(raw["wait"]) if raw.get("wait") is not None else None)


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
    ids = [p.id for p in probes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: duplicate probe ids")
    experiment = data.get("experiment") or (path.parent.name if path.parent.name.startswith("e") else "")
    return Scenario(id=str(data.get("id") or path.stem), lang=str(data.get("lang", "en")), start=start,
                    sessions=sorted(sessions, key=lambda s: s.at), probes=sorted(probes, key=lambda p: p.at),
                    experiment=experiment, description=str(data.get("description", "")), path=path)
