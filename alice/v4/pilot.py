"""P0 — three nodes, one collision (V4 spec §9.3, T128). A development pilot: no time, no gate, cents.

A neutral fact (fast decay), a charged statement said with irritation (slow decay), a later calm statement that
contradicts it, and a trigger that activates both. Three replies with the two statements at equal activations, three
at unequal ones, each from the same saved state. Read by hand: does the reply cite the specific memory; does it waver
when they are close; does it drift between repeats of the same state?
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from ..common.clock import SimClock
from ..common.config import Config
from .agent import AgentV4

START = datetime(2026, 9, 1, 10, 0)
NEUTRAL = "The team moved the test runs to nightly builds."
CHARGED = "Writing tests is just bureaucracy, it slows everything down."   # said with irritation
CALM = "Honestly, the tests saved us last week. I'm glad we have them."    # weeks later, calmly
TRIGGER = "Should we write tests for the new payment module?"
STATES = {"equal": {"charged": 0.6, "calm": 0.6}, "unequal": {"charged": 0.85, "calm": 0.3}}
REPEATS = 3


def run_p0(cfg: Config, out: Path, llm=None, embed=None) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    kwargs = {"sync_writes": True, "extract_after_reply": False, **({"llm": llm} if llm else {}),
              **({"embed": embed} if embed is not None else {})}
    base = out / "p0_base.db"
    agent = AgentV4(cfg, SimClock(START), base, **kwargs)
    ids = {}
    for name, text, valence, arousal in (("neutral", NEUTRAL, 0.0, 0.1), ("charged", CHARGED, -0.6, 0.9),
                                         ("calm", CALM, 0.4, 0.2)):
        mid = agent.store.add_memory(text, importance=0.6, entities=["USER"])
        agent.db.execute("INSERT OR REPLACE INTO memory_affect(memory_id, valence, arousal) VALUES (?, ?, ?)",
                         (mid, valence, arousal))
        ids[name] = mid
    agent._sync()
    agent.substrate.save()
    agent.close()
    results = []
    for state, levels in STATES.items():
        for k in range(1, REPEATS + 1):
            path = out / f"p0_{state}_{k}.db"
            shutil.copy(base, path)
            fork = AgentV4(cfg, SimClock(START), path, **kwargs)
            f = fork.substrate.field
            for name, a in {"neutral": 0.2, **levels}.items():
                f.a[f.node_for("memory", ids[name])] = a
            answer = fork.reply(TRIGGER)
            results.append({"state": state, "repeat": k, "activations": {"neutral": 0.2, **levels},
                            "reply": answer, "memory_block": fork.last_memory_block})
            fork.close()
    path = out / "p0.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
