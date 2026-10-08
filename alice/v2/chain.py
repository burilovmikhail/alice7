"""Reading V2 state back out of the logs (spec §8.2, §8.3).

explain(): for a reply, the V2 state it saw and where each piece came from, down to user messages (E7).
summary(): lesson hygiene, belief drift and narrative inflation over a whole run.
Both read only the database, so they work on saved runs and probe forks.
"""

import json
import sqlite3


def _row(db, sql: str, args=()) -> dict | None:
    r = db.execute(sql, args).fetchone()
    return dict(r) if r else None


def _message(db, message_id) -> dict | None:
    if message_id is None:
        return None
    return _row(db, "SELECT id, session_id, role, content, ts FROM messages WHERE id=?", (message_id,))


def _feedback(db, fid: int) -> dict | None:
    f = _row(db, "SELECT * FROM feedback WHERE id=?", (fid,))
    if f is None:
        return None
    f["reply"], f["reaction"] = _message(db, f["assistant_msg_id"]), _message(db, f["user_msg_id"])
    return f


def explain(db: sqlite3.Connection, message_id: int) -> dict:
    """The causal chain behind one assistant reply. `complete` is True when every shown piece of V2 state
    resolves through logged rows to the messages it came from; `missing` says what doesn't."""
    out = {"message": _message(db, message_id), "lessons": [], "portrait": None, "opinions": [], "intentions": [],
           "missing": []}
    state = _row(db, "SELECT * FROM turn_state WHERE message_id=?", (message_id,))
    out["turn_state"] = state
    if state is None:
        out["missing"].append(f"no turn_state for message {message_id}")
        out["complete"] = False
        return out
    missing = out["missing"]

    for lid in json.loads(state["lesson_ids"]):
        lesson = _row(db, "SELECT id, category, rule, situation, confidence, status FROM lessons WHERE id=?", (lid,))
        if lesson is None:
            missing.append(f"lesson {lid} not found")
            continue
        lesson["events"] = []
        for e in db.execute("SELECT * FROM lesson_events WHERE lesson_id=? ORDER BY id", (lid,)):
            e = dict(e)
            fids = json.loads(e.pop("feedback_ids") or "[]")
            e["feedback"] = [f for f in (_feedback(db, i) for i in fids) if f]
            e["trigger"] = _message(db, e["message_id"])
            grounded = bool(e["trigger"]) or any(f["reply"] and f["reaction"] for f in e["feedback"])
            if not grounded:
                missing.append(f"lesson {lid} {e['op']} (event {e['id']}) has no messages behind it")
            lesson["events"].append(e)
        if not lesson["events"]:
            missing.append(f"lesson {lid} has no events")
        out["lessons"].append(lesson)

    if state["portrait_id"] is not None:
        p = _row(db, "SELECT * FROM portraits WHERE id=?", (state["portrait_id"],))
        if p is None:
            missing.append(f"portrait {state['portrait_id']} not found")
        else:
            if p["source"] == "self_review":
                session = _row(db, "SELECT id, started_at FROM sessions WHERE id=?", (p["session_id"],))
                p["session_messages"] = db.execute("SELECT COUNT(*) FROM messages WHERE session_id=?",
                                                   (p["session_id"],)).fetchone()[0]
                if session is None or not p["session_messages"]:
                    missing.append(f"portrait {p['id']}: its session is gone")
            out["portrait"] = p

    for oid in json.loads(state["opinion_ids"]):
        o = _row(db, "SELECT id, topic, content, stance, session_id, source FROM opinions WHERE id=?", (oid,))
        if o is None:
            missing.append(f"opinion {oid} not found")
        elif o["source"] == "self_review" and not _row(db, "SELECT id FROM sessions WHERE id=?", (o["session_id"],)):
            missing.append(f"opinion {oid}: its session is gone")
        out["opinions"].append(o)

    for iid in json.loads(state["intention_ids"]):
        i = _row(db, "SELECT * FROM intentions WHERE id=?", (iid,))
        if i is None:
            missing.append(f"intention {iid} not found")
            continue
        i["trigger"] = _message(db, i["message_id"])
        if i["source"] == "commitment" and i["trigger"] is None:
            missing.append(f"intention {iid}: the commitment message is gone")
        out["intentions"].append(i)

    out["complete"] = not missing
    out["injected"] = (out["portrait"] or {}).get("source") == "injected" or any(
        o and o["source"] == "injected" for o in out["opinions"])
    return out


def render(chain: dict) -> str:
    """Human-readable chain for the CLI."""
    def short(text, n=160):
        text = " ".join(str(text or "").split())
        return text if len(text) <= n else text[:n] + "…"

    m = chain["message"] or {}
    lines = [f"Reply #{m.get('id')} ({m.get('ts')}): {short(m.get('content'))}"]
    if chain.get("turn_state") is None:
        return "\n".join(lines + ["  (no V2 state recorded)"])
    for l in chain["lessons"]:
        lines.append(f"  lesson #{l['id']} [{l['category']}, {l['status']}, {l['confidence']:.2f}] {l['rule']}"
                     + (f" | when {l['situation']}" if l["situation"] else ""))
        for e in l["events"]:
            lines.append(f"    {e['sim_ts']} {e['op']} -> {e['confidence']:.2f}  {short(e['note'], 100)}")
            if e["trigger"]:
                lines.append(f"      because of message #{e['trigger']['id']}: «{short(e['trigger']['content'], 100)}»")
            for f in e["feedback"]:
                lines.append(f"      reaction #{f['id']} {f['kind']} ({f['signal']:+.1f}) about: {short(f['what'], 80)}")
                if f["reply"]:
                    lines.append(f"        to reply #{f['reply']['id']}: «{short(f['reply']['content'], 100)}»")
                if f["reaction"]:
                    lines.append(f"        user #{f['reaction']['id']}: «{short(f['reaction']['content'], 100)}»")
    if p := chain["portrait"]:
        lines.append(f"  portrait #{p['id']} ({p['source']}, session {p['session_id']}): {short(p['content'])}")
    for o in chain["opinions"]:
        lines.append(f"  opinion #{o['id']} ({o['source']}, session {o['session_id']}) {o['topic']}: {short(o['content'])}")
    for i in chain["intentions"]:
        src = f"message #{i['trigger']['id']}" if i.get("trigger") else f"session {i['session_id']}"
        lines.append(f"  intention #{i['id']} ({i['source']}, from {src}): {short(i['content'])}")
    lines.append("  chain complete" if chain["complete"] else "  INCOMPLETE: " + "; ".join(chain["missing"]))
    return "\n".join(lines)


def summary(db: sqlite3.Connection) -> dict:
    """Lesson hygiene, belief drift and narrative inflation (spec §8.2), from one agent database."""
    q = lambda sql, args=(): db.execute(sql, args).fetchall()
    events = {r[0]: r[1] for r in q("SELECT op, COUNT(*) FROM lesson_events GROUP BY op")}
    lessons = {
        "active": q("SELECT COUNT(*) FROM lessons WHERE status='active'")[0][0],
        "habits": q("SELECT COUNT(*) FROM lessons WHERE status='active' AND situation='' AND confidence >= 0.55")[0][0],
        "retired": q("SELECT COUNT(*) FROM lessons WHERE status='retired'")[0][0],
        "events": events,
        "by_category": {r[0]: r[1] for r in q("SELECT category, COUNT(*) FROM lessons WHERE status='active' "
                                              "GROUP BY category")},
    }
    feedback = {"total": q("SELECT COUNT(*) FROM feedback")[0][0],
                "by_kind": {r[0]: r[1] for r in q("SELECT kind, COUNT(*) FROM feedback GROUP BY kind")}}

    portraits = q("SELECT id, created_at, source FROM portraits ORDER BY id")
    drift, inflation = [], []
    for prev, cur in zip(portraits, portraits[1:]):
        before = {b["id"]: b for b in q("SELECT * FROM beliefs WHERE portrait_id=?", (prev["id"],))}
        after = q("SELECT * FROM beliefs WHERE portrait_id=?", (cur["id"],))
        continued = [b for b in after if b["parent_id"] in before]
        # Evidence between the two versions: reactions or lesson changes. A belief that grows without any is the
        # narrative reinforcing itself (the V4 motivation, measured where it first appears)
        evidence = q("SELECT COUNT(*) FROM feedback WHERE created_at > ? AND created_at <= ?",
                     (prev["created_at"], cur["created_at"]))[0][0] + \
            q("SELECT COUNT(*) FROM lesson_events WHERE sim_ts > ? AND sim_ts <= ?",
              (prev["created_at"], cur["created_at"]))[0][0]
        grew = [b for b in continued if b["weight"] > before[b["parent_id"]]["weight"] + 1e-9]
        drift.append({"portrait": cur["id"], "continued": len(continued), "new": len(after) - len(continued),
                      "dropped": len(set(before) - {b["parent_id"] for b in continued}),
                      "weight_up": len(grew), "evidence_between": evidence})
        if not evidence:
            inflation += [{"portrait": cur["id"], "belief": b["text"],
                           "from": before[b["parent_id"]]["weight"], "to": b["weight"]} for b in grew]
    return {
        "lessons": lessons, "feedback": feedback,
        "portraits": {"versions": len(portraits),
                      "injected": sum(1 for p in portraits if p["source"] == "injected")},
        "belief_drift": drift, "narrative_inflation": inflation,
        "opinions": {"active": q("SELECT COUNT(*) FROM opinions WHERE superseded_by IS NULL")[0][0],
                     "superseded": q("SELECT COUNT(*) FROM opinions WHERE superseded_by IS NOT NULL")[0][0]},
        "intentions": {r[0]: r[1] for r in q("SELECT status, COUNT(*) FROM intentions GROUP BY status")},
    }
