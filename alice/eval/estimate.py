"""Pre-launch cost estimate: count calls per scenario × condition, rough tokens per call, OpenRouter prices.

Deliberately crude: it exists so a battery is never launched blind. After a pilot run, `report` gives the
measured cost per run and extrapolates the battery from that, which supersedes this estimate.
"""

import json
import math
import urllib.request
from datetime import timedelta

from ..common.config import Config
from ..v2.config import load_v2_config
from ..v3.config import load_v3_config
from .scenario import Scenario

# Rough token sizes per call (prompt, completion)
PERSONA = 250
MSG = 60            # an average user message
REPLY = 250
HIST = (MSG + REPLY) // 2   # an average message in history: half of them are replies
V1_CHAT_EXTRA = 300 + 900   # core facts + <memory> block
EXTRACT = (1500, 250)
FOLD = (700, 200)
EPISODE_BASE = (1500, 200)
CARRYOVER_BASE = (800, 400)
JUDGE = (450, 60)
EMBED_TOKENS = 60
# Conditions built on V1 memory
MEMORY_AGENTS = ("V1", "V2", "V3", "V4")
V2_FAMILY = ("V2", "V3", "V4")
# V3: per turn one more cheap observation and one stream thought; in silence stream ticks, wakes, nightly sleep
OBSERVE_V3 = (600, 80)
STREAM = (800, 60)
WAKE = (2500, 400)
SLEEP_CALLS = 3.5           # NREM (only with near-duplicates), REM, lessons, portrait of the day
SLEEP_CALL = (2000, 400)
WAKES_PER_SILENT_DAY = 1    # rough: one right after a conversation ends, about one more per silent awake day
# V4: per turn one cheap observation (appraisal, intentions, reaction) and a trace embedding; no reflector, no
# per-session self-review. In silence no model at all until the gate fires; counted at the caps (an upper bound).
# Per night: the narrative review, one cheap dissonance check, up to two dreams.
OBSERVE_V4 = (900, 120)
NARRATIVE = (3000, 600)
DISSONANCE = (2000, 200)
DREAM = (700, 100)
DREAMS_PER_NIGHT = 2
CARRYOVER_AGENTS = ("B2", "B3")
# V2 on top of V1: prompt sections, per-turn self-observation, session-end reflection and self-review
V2_CHAT_EXTRA = 350
OBSERVE = (1100, 120)
REFLECT = (2500, 400)      # counted every session: an upper bound, it runs only when there are reactions
SELFREVIEW = (3500, 600)
B3_EXTRA = 150             # the how_i_talk notes


def fetch_prices(models: set[str]) -> dict[str, tuple[float, float]]:
    """$ per token (prompt, completion) from OpenRouter's public model lists; missing models are omitted."""
    prices = {}
    for url in ("https://openrouter.ai/api/v1/models", "https://openrouter.ai/api/v1/embeddings/models"):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                data = json.load(resp)["data"]
        except Exception:
            continue
        for m in data:
            if m.get("id") in models and m.get("pricing"):
                p = m["pricing"]
                prices[m["id"]] = (float(p.get("prompt") or 0), float(p.get("completion") or 0))
    return prices


def calls(scenario: Scenario, condition: str, cfg: Config, judge: bool) -> list[tuple[str, int, int]]:
    """[(role, prompt_tokens, completion_tokens)] for one run; role is chat|fast|observe|reflect|embed|judge."""
    v2 = condition in V2_FAMILY
    v3 = condition == "V3"
    v4 = condition == "V4"
    notes = 400 + (B3_EXTRA if condition == "B3" else 0)
    notes_role = "reflect" if condition == "B3" else "fast"
    out: list[tuple[str, int, int]] = []
    history_all = 0
    for spec in scenario.sessions:
        n = len(spec.turns)
        for i in range(n):
            in_session = min(2 * i, cfg.short_term) if condition in MEMORY_AGENTS else 2 * i
            if condition in MEMORY_AGENTS:
                out.append(("chat", PERSONA + V1_CHAT_EXTRA + (V2_CHAT_EXTRA if v2 else 0) + in_session * HIST + MSG,
                            REPLY))
                out.append(("fast", *EXTRACT))
                out.append(("embed", EMBED_TOKENS * 4, 0))
                if v2 and not v4:
                    out.append(("observe", *OBSERVE))
                if v3:
                    out += [("fast", *OBSERVE_V3), ("stream", *STREAM)]
                if v4:
                    out += [("observe", *OBSERVE_V4), ("embed", EMBED_TOKENS, 0)]
            elif condition == "B1":
                out.append(("chat", PERSONA + (history_all + 2 * i) * HIST + MSG, REPLY))
            elif condition in CARRYOVER_AGENTS:
                out.append(("chat", PERSONA + notes + in_session * HIST + MSG, REPLY))
            else:
                out.append(("chat", PERSONA + in_session * HIST + MSG, REPLY))
        history_all += 2 * n
        if condition in MEMORY_AGENTS:
            out += [("fast", *FOLD)] * max(0, math.ceil((2 * n - cfg.short_term) / (cfg.short_term // 2 or 1)))
            out.append(("fast", EPISODE_BASE[0] + 2 * n * HIST, EPISODE_BASE[1]))
            if v2 and not v4:
                out += [("reflect", *REFLECT), ("reflect", SELFREVIEW[0] + 2 * n * HIST, SELFREVIEW[1])]
        elif condition in CARRYOVER_AGENTS:
            out.append((notes_role, CARRYOVER_BASE[0] + 2 * n * HIST, CARRYOVER_BASE[1]))
    closed = set()  # probes at the same time share one session close (runner._closed_base)
    if v3:
        out += silence_calls(scenario, cfg)
    if v4:
        out += silence_calls_v4(scenario, cfg)
    for probe in scenario.probes:
        first_at_time = probe.new_session and probe.at not in closed
        if probe.new_session:
            closed.add(probe.at)
        if condition in MEMORY_AGENTS:
            out.append(("chat", PERSONA + V1_CHAT_EXTRA + (V2_CHAT_EXTRA if v2 else 0) + MSG, REPLY))
            out.append(("embed", EMBED_TOKENS, 0))
            if first_at_time:
                out.append(("fast", *EPISODE_BASE))  # the fork finalizes the open session
                if v2 and not v4:  # ...and runs the session-end V2 steps, as a returning user would trigger them
                    out += [("reflect", *REFLECT), ("reflect", *SELFREVIEW)]
        elif condition == "B1":
            out.append(("chat", PERSONA + history_all * HIST + MSG, REPLY))
        else:
            out.append(("chat", PERSONA + (notes if condition in CARRYOVER_AGENTS else 0) + MSG, REPLY))
            if condition in CARRYOVER_AGENTS and first_at_time:
                out.append((notes_role, *CARRYOVER_BASE))
        if judge:
            out += [("judge", *JUDGE)] * len(probe.judge)
    return out


def _silences(scenario: Scenario, cfg: Config):
    """(start, end) of every stretch of silence on the main timeline and before each probe time (probe bases relive
    the silence from the last main event before them)."""
    from ..eval.scenario import TURN_GAP
    gap = timedelta(hours=cfg.session_gap_hours)
    ends = []
    for spec in scenario.sessions:
        at = scenario.start + spec.at
        ends.append((at, at + TURN_GAP * len(spec.turns)))
    out = [(e + gap, nxt) for (_, e), (nxt, _) in zip(ends, ends[1:]) if nxt > e + gap]
    for t in sorted({scenario.start + p.at for p in scenario.probes if p.new_session}):
        before = [e for s0, e in ends if s0 <= t]
        if before and t > before[-1] + gap:
            out.append((before[-1] + gap, t))
    return out


def silence_calls(scenario: Scenario, cfg: Config) -> list[tuple[str, int, int]]:
    v3 = load_v3_config()
    out = []
    for a, b in _silences(scenario, cfg):
        hours = (b - a).total_seconds() / 3600
        t, ticks, nights = a, 0, 0
        while t < b:  # count stream ticks by the rhythm, and nightly sleeps
            awake = v3.awake_from <= t.time() < v3.awake_to
            step = timedelta(minutes=v3.stream_idle_min if awake else v3.stream_asleep_min)
            ticks += 1
            nxt_sleep = t.replace(hour=v3.sleep_at.hour, minute=v3.sleep_at.minute, second=0)
            if t < nxt_sleep <= min(t + step, b):
                nights += 1
            t += step
        wakes = 1 + int(hours // 24) * WAKES_PER_SILENT_DAY
        out += [("stream", *STREAM)] * ticks + [("wake", *WAKE)] * wakes
        out += [("wake", *SLEEP_CALL)] * round(nights * SLEEP_CALLS)
    return out


def silence_calls_v4(scenario: Scenario, cfg: Config) -> list[tuple[str, int, int]]:
    """Gate firings at the daily cap (an upper bound: usually fewer), and the night's calls."""
    v3 = load_v3_config()
    out = []
    for a, b in _silences(scenario, cfg):
        days = (b - a).total_seconds() / 86400
        nights = sum(1 for k in range(int(days) + 2)
                     if a < (a.replace(hour=2, minute=0, second=0) + timedelta(days=k)) <= b)
        out += [("wake", *WAKE)] * math.ceil(days * v3.wakes_per_day)
        out += [("reflect", *NARRATIVE), ("observe", *DISSONANCE)] * nights
        out += [("wake", *DREAM)] * (nights * DREAMS_PER_NIGHT)
    return out


def estimate(scenarios: list[Scenario], conditions: list[str], cfg: Config, n: int, judge: bool = True) -> str:
    models = {"chat": cfg.chat_model, "fast": cfg.fast_model, "embed": cfg.embed_model, "judge": cfg.judge_model,
              **load_v2_config().models(cfg), **load_v3_config().models(cfg)}
    prices = fetch_prices(set(models.values()))
    lines = ["| condition | runs | calls | prompt tok | completion tok | est. $ |", "|---|---|---|---|---|---|"]
    grand = 0.0
    for cond in conditions:
        tot_calls = tot_in = tot_out = 0
        cost = 0.0
        for sc in scenarios:
            for role, p, c in calls(sc, cond, cfg, judge):
                price = prices.get(models[role], (0.0, 0.0))
                tot_calls += 1
                tot_in += p
                tot_out += c
                cost += p * price[0] + c * price[1]
        lines.append(f"| {cond} | {len(scenarios) * n} | {tot_calls * n} | {tot_in * n:,} | {tot_out * n:,} | "
                     f"{cost * n:.2f} |")
        grand += cost * n
    missing = [m for m in set(models.values()) if m not in prices and m != "none"]
    notes = [f"\nTotal ≈ ${grand:.2f} for {len(scenarios)} scenarios × {len(conditions)} conditions × N={n}."]
    if missing:
        notes.append(f"No OpenRouter price found for: {', '.join(sorted(missing))} (counted as $0). "
                     "Check the model ids.")
    notes.append("Rough heuristic; after a pilot run use `alice-v1 report` for measured cost per run.")
    return "\n".join(lines + notes)
