"""Offline fakes: a scripted LLM (goes through the real tracing code) and a deterministic embedder."""

import json
import zlib
from datetime import datetime

import numpy as np
import pytest

from alice.common.clock import SimClock
from alice.common.config import Config
from alice.common.db import connect
from alice.common.llm import LLM
from alice.common.text import stem, words
from alice.common.trace import Tracer
from alice.v1.store import MemoryStore

START = datetime(2026, 1, 5, 10, 0)  # a Monday


def fake_embed(texts):
    """Bag of stems hashed into 256 dims: similar texts -> close vectors. crc32, since hash() is salted."""
    out = np.zeros((len(texts), 256), dtype=np.float32)
    for i, t in enumerate(texts):
        for w in words(t):
            out[i, zlib.crc32(stem(w).encode()) % 256] += 1
    return out / np.linalg.norm(out, axis=1, keepdims=True).clip(min=1e-9)


DEFAULT_REPLIES = {
    "chat": "Okay.",
    "extract": {},
    "fold": "Summary of the earlier part.",
    "episode": {},
    "carryover": {},
    "judge": {"score": 1, "reason": "fine"},
}


class FakeLLM(LLM):
    """Replies per purpose: a value, a list (consumed in order), or a callable(kwargs) -> value.
    dict values are returned as JSON text. Every request is kept in .requests."""

    def __init__(self, replies: dict | None = None, cfg: Config | None = None):
        super().__init__(cfg or make_cfg(), client=object())
        self.replies = {**DEFAULT_REPLIES, **(replies or {})}
        self.requests: list[tuple[str, dict]] = []
        self.embed_calls: list[list[str]] = []

    def _request(self, kwargs, purpose):
        self.requests.append((purpose, kwargs))
        value = self.replies.get(purpose, "")
        if isinstance(value, list):
            value = value.pop(0) if value else ""
        if callable(value):
            value = value(kwargs)
        if isinstance(value, Exception):
            raise value
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
        return text, {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.001}

    def _embed_request(self, texts, model):
        self.embed_calls.append(list(texts))
        return fake_embed(texts), {"prompt_tokens": len(texts), "cost": 0.0}

    def prompts(self, purpose: str) -> list[dict]:
        return [k for p, k in self.requests if p == purpose]


def make_cfg(**overrides) -> Config:
    base = dict(api_key="test", embed_model="fake", db_path=None, sync_writes=True)
    base.update(overrides)
    return Config(**base)


def user_content(kwargs) -> str:
    return kwargs["messages"][-1]["content"]


@pytest.fixture
def clock():
    return SimClock(START)


@pytest.fixture
def store(tmp_path, clock):
    db = connect(tmp_path / "m.db")
    return MemoryStore(db, clock, fake_embed, Tracer(db, clock))
