"""Configuration: `.env` + defaults -> frozen Config."""

import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

BASE_URL = "https://openrouter.ai/api/v1"

DEFAULTS = {
    "ALICE_CHAT_MODEL": "anthropic/claude-sonnet-5",
    "ALICE_FAST_MODEL": "google/gemini-3.5-flash-lite",
    "ALICE_EMBED_MODEL": "baai/bge-m3",
    "ALICE_JUDGE_MODEL": "openai/gpt-5",
    "ALICE_CHAT_TEMPERATURE": "0.7",
    "ALICE_DB": "data/v1/memory.db",
    "ALICE_SHORT_TERM": "12",
    "ALICE_CORE_BUDGET": "600",
    "ALICE_RETRIEVAL_BUDGET": "1500",
    "ALICE_SESSION_GAP_HOURS": "3",
    "ALICE_B1_MAX_TOKENS": "150000",
}


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    api_key: str = ""
    base_url: str = BASE_URL
    chat_model: str = DEFAULTS["ALICE_CHAT_MODEL"]
    fast_model: str = DEFAULTS["ALICE_FAST_MODEL"]
    embed_model: str = DEFAULTS["ALICE_EMBED_MODEL"]
    judge_model: str = DEFAULTS["ALICE_JUDGE_MODEL"]
    chat_temperature: float = 0.7
    seed: int | None = None
    # OpenRouter provider.order pin; empty = let OpenRouter route
    provider_order: tuple[str, ...] = field(default_factory=tuple)
    db_path: Path = Path(DEFAULTS["ALICE_DB"])
    # Messages kept verbatim before the oldest half is folded into the rolling summary
    short_term: int = 12
    core_budget: int = 600
    retrieval_budget: int = 1500
    session_gap_hours: float = 3.0
    # None = interface default (CLI: background, eval: inline)
    sync_writes: bool | None = None
    # B1 baseline: transcript cap in estimated tokens
    b1_max_tokens: int = 150_000

    def public(self) -> dict:
        """Everything except the key, for run manifests."""
        d = asdict(self)
        d.pop("api_key")
        d["db_path"] = str(self.db_path)
        d["provider_order"] = list(self.provider_order)
        return d

    def with_(self, **changes) -> "Config":
        return replace(self, **changes)


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else DEFAULTS.get(name)


def load_config(*, require_key: bool = True, env_file: str | Path | None = None) -> Config:
    load_dotenv(env_file or Path.cwd() / ".env")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if require_key and (not api_key or api_key.endswith("...")):
        raise ConfigError("OPENROUTER_API_KEY is not set. Copy .env.example to .env and put your OpenRouter key there.")
    seed = os.getenv("ALICE_SEED")
    sync = os.getenv("ALICE_SYNC_WRITES")
    order = os.getenv("ALICE_PROVIDER_ORDER", "")
    return Config(
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL") or BASE_URL,
        chat_model=_env("ALICE_CHAT_MODEL"),
        fast_model=_env("ALICE_FAST_MODEL"),
        embed_model=_env("ALICE_EMBED_MODEL"),
        judge_model=_env("ALICE_JUDGE_MODEL"),
        chat_temperature=float(_env("ALICE_CHAT_TEMPERATURE")),
        seed=int(seed) if seed else None,
        provider_order=tuple(p.strip() for p in order.split(",") if p.strip()),
        db_path=Path(_env("ALICE_DB")),
        short_term=int(_env("ALICE_SHORT_TERM")),
        core_budget=int(_env("ALICE_CORE_BUDGET")),
        retrieval_budget=int(_env("ALICE_RETRIEVAL_BUDGET")),
        session_gap_hours=float(_env("ALICE_SESSION_GAP_HOURS")),
        sync_writes=None if sync in (None, "") else sync.strip() not in ("0", "false", "no"),
        b1_max_tokens=int(_env("ALICE_B1_MAX_TOKENS")),
    )
