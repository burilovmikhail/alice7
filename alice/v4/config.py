"""V4 settings (kept here so the shared code, V2 and V3 stay free of V4 terms)."""

import hashlib
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import constants as K
from .switches import V4Switches

CONSTANTS_PATH = Path(K.__file__)
DRIVE_SETS = ("full", "minimal")
URGENCY_COUNTS = ("kinds", "nodes")


@dataclass(frozen=True)
class V4Config:
    seed: int = 0                     # noise generator seed (D11)
    dt_min: float = K.DT_MIN
    drive_set: str = "full"           # full | minimal (sleep pressure, arousal, social need): Q11
    urgency_count: str = "kinds"      # kinds | nodes: what counts as independent urgency sources (Q2)
    switches: V4Switches = field(default_factory=V4Switches)

    def public(self) -> dict:
        d = asdict(self)
        d["switches"] = self.switches.as_dict()
        d["constants"] = constants_version()
        return d


def constants_version() -> dict:
    """Which constants a run used (spec §4.4): the file's hash and the last commit that touched it."""
    text = CONSTANTS_PATH.read_bytes()
    try:
        commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(CONSTANTS_PATH)], capture_output=True,
                                text=True, check=True, cwd=CONSTANTS_PATH.parent).stdout.strip() or None
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", str(CONSTANTS_PATH)], capture_output=True,
                                    text=True, check=True, cwd=CONSTANTS_PATH.parent).stdout.strip())
    except Exception:
        commit, dirty = None, None
    return {"sha256": hashlib.sha256(text).hexdigest()[:16], "commit": commit, "dirty": dirty}


def load_v4_config() -> V4Config:
    def get(name: str) -> str | None:
        value = os.getenv(name)
        return value if value not in (None, "") else None

    drive_set = (get("ALICE_V4_DRIVES") or "full").lower()
    urgency = (get("ALICE_V4_URGENCY") or "kinds").lower()
    if drive_set not in DRIVE_SETS:
        raise ValueError(f"ALICE_V4_DRIVES must be one of {DRIVE_SETS}")
    if urgency not in URGENCY_COUNTS:
        raise ValueError(f"ALICE_V4_URGENCY must be one of {URGENCY_COUNTS}")
    return V4Config(seed=int(get("ALICE_V4_SEED") or 0), dt_min=float(get("ALICE_V4_DT_MIN") or K.DT_MIN),
                    drive_set=drive_set, urgency_count=urgency, switches=V4Switches.parse(get("ALICE_V4_SWITCHES")))
