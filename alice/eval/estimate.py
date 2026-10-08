"""Pre-launch cost estimate: count calls per scenario × condition, rough tokens per call, OpenRouter prices.

Deliberately crude: it exists so a battery is never launched blind. After a pilot run, `report` gives the
measured cost per run and extrapolates the battery from that, which supersedes this estimate.
"""

import json
import math
import urllib.request

from ..common.config import Config
from ..v2.config import load_v2_config
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
MEMORY_AGENTS = ("V1", "V2")
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
    v2 = condition == "V2"
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
                if v2:
                    out.append(("observe", *OBSERVE))
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
            if v2:
                out += [("reflect", *REFLECT), ("reflect", SELFREVIEW[0] + 2 * n * HIST, SELFREVIEW[1])]
        elif condition in CARRYOVER_AGENTS:
            out.append((notes_role, CARRYOVER_BASE[0] + 2 * n * HIST, CARRYOVER_BASE[1]))
    closed = set()  # probes at the same time share one session close (runner._closed_base)
    for probe in scenario.probes:
        first_at_time = probe.new_session and probe.at not in closed
        if probe.new_session:
            closed.add(probe.at)
        if condition in MEMORY_AGENTS:
            out.append(("chat", PERSONA + V1_CHAT_EXTRA + (V2_CHAT_EXTRA if v2 else 0) + MSG, REPLY))
            out.append(("embed", EMBED_TOKENS, 0))
            if first_at_time:
                out.append(("fast", *EPISODE_BASE))  # the fork finalizes the open session
                if v2:  # ...and runs the session-end V2 steps, as a returning user would trigger them
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


def estimate(scenarios: list[Scenario], conditions: list[str], cfg: Config, n: int, judge: bool = True) -> str:
    models = {"chat": cfg.chat_model, "fast": cfg.fast_model, "embed": cfg.embed_model, "judge": cfg.judge_model,
              **load_v2_config().models(cfg)}
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
