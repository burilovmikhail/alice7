"""Scoring: deterministic checks and behavioral counters first, then an LLM judge with a per-probe rubric."""

import re

from ..common.llm import LLM

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⭐❤]")
BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.M)
HEADER_RE = re.compile(r"^\s*#{1,6}\s+", re.M)


def measures(text: str) -> dict[str, float]:
    """Automatically measurable behavior (E4)."""
    words = re.findall(r"\w+", text, re.U)
    sentences = [s for s in re.split(r"[.!?…]+", text) if s.strip()]
    return {
        "chars": len(text),
        "words": len(words),
        "sentences": len(sentences),
        "bullets": len(BULLET_RE.findall(text)),
        "headers": len(HEADER_RE.findall(text)),
        "emoji": len(EMOJI_RE.findall(text)),
        "questions": text.count("?"),
        "exclamations": text.count("!"),
    }


def _as_list(v) -> list[str]:
    return [str(x) for x in (v if isinstance(v, list) else [v])]


def check(text: str, expect: dict) -> dict[str, bool]:
    """Every expectation -> pass/fail. Case-insensitive substring matching (use stems: "Москв")."""
    low = text.lower()
    m = measures(text)
    out: dict[str, bool] = {}
    for key, value in expect.items():
        if key == "contains_any":
            out[key] = any(s.lower() in low for s in _as_list(value))
        elif key == "contains_all":
            out[key] = all(s.lower() in low for s in _as_list(value))
        elif key == "not_contains":
            out[key] = not any(s.lower() in low for s in _as_list(value))
        elif key == "regex":
            out[key] = all(re.search(p, text, re.I | re.S) for p in _as_list(value))
        elif key == "not_regex":
            out[key] = not any(re.search(p, text, re.I | re.S) for p in _as_list(value))
        elif key.startswith(("max_", "min_")) and key[4:] in m:
            n = m[key[4:]]
            out[key] = n <= value if key.startswith("max_") else n >= value
        else:
            raise ValueError(f"unknown expectation: {key}")
    return out


JUDGE_PROMPT = """You grade one reply of a conversational assistant in a memory evaluation. You don't know which
system produced it; judge only the reply against the rubric.

Score 1 if the reply fully satisfies the rubric, 0.5 if it partially does, 0 if it doesn't.
Reply with a JSON object: {"score": 0 | 0.5 | 1, "reason": "one sentence"}"""


def judge(llm: LLM, rubric: str, ask: str, reply: str) -> dict:
    data = llm.json(JUDGE_PROMPT, f"Rubric: {rubric}\n\nUser's message:\n{ask}\n\nAssistant's reply:\n{reply}",
                    purpose="judge", model=llm.cfg.judge_model, temperature=0)
    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        return {"score": None, "reason": f"unparseable judge output: {data!r}"}
    score = min((0.0, 0.5, 1.0), key=lambda s: abs(s - score))
    return {"score": score, "reason": str(data.get("reason", ""))}
