"""Reading the field log back (spec §8): what the operator's commands and the report show. Read-only (D7 holds for
the agent: none of this reaches a prompt)."""

import json
import sqlite3


def top_nodes(agent, n: int = 12) -> list[str]:
    """The most active nodes now, with why they may be up (kind, base level, unfinishedness, refractory)."""
    s = agent.substrate
    f, t = s.field, s.t or 0.0
    order = sorted(range(len(f)), key=lambda i: -f.a[i])[:n]
    out = []
    for i in order:
        why = [f.describe(i, t)]
        if f.u[i] > 0:
            why.append(f"unfinished {f.u[i]:.1f}")
        if f.refractory_until[i] > t:
            why.append("refractory")
        if i in s.attention.focus_set:
            why.append("in focus")
        out.append(f"{f.a[i]:.2f}  [{int(f.ids[i])}] ({', '.join(why)}; B {f.B[i]:.1f}, salience {f.salience[i]:.2f}) "
                   f"{f.label[i][:90]}")
    return out


def gate_state(agent) -> list[str]:
    s = agent.substrate
    r = s.last
    lines = [f"coherence {r.coherence:.3f} (energy {r.energy:.3f} × stability {r.stability:.2f}) vs θ {r.theta:.3f}; "
             f"urgency {r.urgency:.3f} vs brake {r.brake:.3f}; focus {s.attention.focus:.2f}",
             "sources: " + ", ".join(f"{k} {v:.2f}" for k, v in r.sources.items())]
    for row in agent.db.execute("SELECT at, kind, cause, thought FROM v4_firings ORDER BY id DESC LIMIT 8"):
        lines.append(f"  {row['at'][5:16]} {row['kind']:6} {row['cause'] or '':12} {row['thought'][:80]}")
    return lines


def steps(db: sqlite3.Connection, start: str | None = None, end: str | None = None) -> list[dict]:
    where, args = [], []
    if start:
        where.append("at >= ?")
        args.append(start)
    if end:
        where.append("at <= ?")
        args.append(end)
    sql = "SELECT * FROM v4_steps" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY rowid"
    return [{**dict(r), "drives": json.loads(r["drives"]), "top": json.loads(r["top"])} for r in db.execute(sql, args)]
