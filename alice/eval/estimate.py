"""Pre-launch cost estimate: count calls per scenario × condition, rough tokens per call, OpenRouter prices.

Deliberately crude: it exists so a battery is never launched blind. After a pilot run, `report` gives the
measured cost per run and extrapolates the battery from that, which supersedes this estimate.
"""

import json
import math
import urllib.request

from ..common.config import Config
from .scenario import Scenario

# Rough token sizes per call (prompt, completion)
PERSONA = 250
MSG = 60            # an average message
REPLY = 250
V1_CHAT_EXTRA = 300 + 900   # core facts + <memory> block
EXTRACT = (1500, 250)
FOLD = (700, 200)
EPISODE_BASE = (1500, 200)
CARRYOVER_BASE = (800, 400)
JUDGE = (450, 60)
EMBED_TOKENS = 60


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
    """[(role, prompt_tokens, completion_tokens)] for one run; role is chat|fast|embed|judge."""
    out: list[tuple[str, int, int]] = []
    history_all = 0
    for spec in scenario.sessions:
        n = len(spec.turns)
        for i in range(n):
            in_session = min(2 * i, cfg.short_term) if condition == "V1" else 2 * i
            if condition == "V1":
                out.append(("chat", PERSONA + V1_CHAT_EXTRA + in_session * MSG + MSG, REPLY))
                out.append(("fast", *EXTRACT))
                out.append(("embed", EMBED_TOKENS * 4, 0))
            elif condition == "B1":
                out.append(("chat", PERSONA + (history_all + 2 * i) * MSG + MSG, REPLY))
            elif condition == "B2":
                out.append(("chat", PERSONA + 400 + in_session * MSG + MSG, REPLY))
            else:
                out.append(("chat", PERSONA + in_session * MSG + MSG, REPLY))
        history_all += 2 * n
        if condition == "V1":
            out += [("fast", *FOLD)] * max(0, math.ceil((2 * n - cfg.short_term) / (cfg.short_term // 2 or 1)))
            out.append(("fast", EPISODE_BASE[0] + 2 * n * MSG, EPISODE_BASE[1]))
        elif condition == "B2":
            out.append(("fast", CARRYOVER_BASE[0] + 2 * n * MSG, CARRYOVER_BASE[1]))
    for probe in scenario.probes:
        if condition == "V1":
            out.append(("chat", PERSONA + V1_CHAT_EXTRA + MSG, REPLY))
            out.append(("embed", EMBED_TOKENS, 0))
            if probe.new_session:
                out.append(("fast", *EPISODE_BASE))  # the fork finalizes the open session
        elif condition == "B1":
            out.append(("chat", PERSONA + history_all * MSG + MSG, REPLY))
        else:
            out.append(("chat", PERSONA + (400 if condition == "B2" else 0) + MSG, REPLY))
            if condition == "B2" and probe.new_session:
                out.append(("fast", *CARRYOVER_BASE))
        if judge:
            out += [("judge", *JUDGE)] * len(probe.judge)
    return out


def estimate(scenarios: list[Scenario], conditions: list[str], cfg: Config, n: int, judge: bool = True) -> str:
    models = {"chat": cfg.chat_model, "fast": cfg.fast_model, "embed": cfg.embed_model, "judge": cfg.judge_model}
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
