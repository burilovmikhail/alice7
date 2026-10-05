"""Scenario format: scripted sessions on a simulated timeline plus probes run on forks of the state."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from ..common.clock import parse_offset

TURN_GAP = timedelta(minutes=2)  # default simulated time between turns


@dataclass
class Turn:
    user: str
    wait: timedelta | None = None  # extra simulated time before this turn


@dataclass
class SessionSpec:
    at: timedelta
    turns: list[Turn]
    new_session: bool = False  # force a boundary even if the silence is shorter than the session gap


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


def load_scenario(path: Path | str) -> Scenario:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    start = data["start"]
    start = start if isinstance(start, datetime) else datetime.fromisoformat(str(start))
    sessions = [SessionSpec(parse_offset(s.get("at", 0)), [_turn(t) for t in s["turns"]],
                            bool(s.get("new_session", False))) for s in data.get("sessions", [])]
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
