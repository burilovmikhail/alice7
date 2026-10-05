"""OpenRouter client (OpenAI-compatible API): chat, JSON completion, embeddings — every call traced with cost."""

import json
import re
import time

import numpy as np

from .config import Config
from .trace import Tracer


class LLM:
    """One client shared across agents; `bind(tracer)` gives a view that logs into a given agent's trace."""

    def __init__(self, cfg: Config, tracer: Tracer | None = None, client=None):
        self.cfg = cfg
        self.tracer = tracer
        self._client = client
        self._no_json_mode: set[str] = set()

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.cfg.api_key, base_url=self.cfg.base_url,
                                  default_headers={"HTTP-Referer": "https://github.com/alice7", "X-Title": "alice7-v1"})
        return self._client

    def bind(self, tracer: Tracer | None) -> "LLM":
        other = object.__new__(type(self))
        other.__dict__.update(self.__dict__)
        other.tracer = tracer
        return other

    # ---------- public API ----------

    def chat(self, messages: list[dict], *, purpose: str = "chat", model: str | None = None,
             temperature: float | None = None, json_mode: bool = False, max_tokens: int | None = None) -> str:
        model = model or self.cfg.chat_model
        kwargs = {"model": model, "messages": messages,
                  "temperature": self.cfg.chat_temperature if temperature is None else temperature}
        if self.cfg.seed is not None:
            kwargs["seed"] = self.cfg.seed
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        extra = {"usage": {"include": True}}
        if self.cfg.provider_order:
            extra["provider"] = {"order": list(self.cfg.provider_order), "allow_fallbacks": False}
        kwargs["extra_body"] = extra
        if json_mode and model not in self._no_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        try:
            try:
                content, usage = self._request(kwargs, purpose)
            except Exception as e:
                if "response_format" not in kwargs or "response_format" not in str(e):
                    raise
                self._no_json_mode.add(model)  # provider without JSON mode: parse JSON out of plain text
                kwargs.pop("response_format")
                content, usage = self._request(kwargs, purpose)
        except Exception as e:
            self._trace(purpose, model, kwargs, None, {}, start, f"{type(e).__name__}: {e}")
            raise
        self._trace(purpose, model, kwargs, content, usage, start, None)
        return content

    def complete(self, system: str, user: str, *, purpose: str, model: str | None = None,
                 temperature: float = 0.3) -> str:
        """One-shot request, fast model by default."""
        return self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                         purpose=purpose, model=model or self.cfg.fast_model, temperature=temperature).strip()

    def json(self, system: str, user: str, *, purpose: str, model: str | None = None,
             temperature: float = 0.0) -> dict:
        """Request expecting a JSON object; {} if it can't be parsed."""
        text = self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                         purpose=purpose, model=model or self.cfg.fast_model, temperature=temperature,
                         json_mode=True)
        return parse_json(text)

    def embed(self, texts: list[str], model: str | None = None) -> np.ndarray:
        model = model or self.cfg.embed_model
        start = time.monotonic()
        request = {"model": model, "input": texts}
        try:
            vectors, usage = self._embed_request(texts, model)
        except Exception as e:
            self._trace("embed", model, request, None, {}, start, f"{type(e).__name__}: {e}")
            raise
        self._trace("embed", model, request, f"{len(vectors)} x {vectors.shape[1] if len(vectors) else 0}",
                    usage, start, None)
        return normalize(vectors)

    # ---------- transport (overridden by test fakes) ----------

    def _request(self, kwargs: dict, purpose: str) -> tuple[str, dict]:
        resp = self.client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or ""), _usage(resp)

    def _embed_request(self, texts: list[str], model: str) -> tuple[np.ndarray, dict]:
        resp = self.client.embeddings.create(model=model, input=texts, extra_body={"usage": {"include": True}})
        return np.array([d.embedding for d in resp.data], dtype=np.float32), _usage(resp)

    def _trace(self, purpose, model, kwargs, content, usage, start, error) -> None:
        if self.tracer is None:
            return
        request = {k: v for k, v in kwargs.items() if k != "extra_body"}
        if "extra_body" in kwargs and "provider" in kwargs["extra_body"]:
            request["provider"] = kwargs["extra_body"]["provider"]
        self.tracer.llm_call(purpose=purpose, model=model, request=request, response=content,
                             prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                             cost=usage.get("cost"), latency_ms=int((time.monotonic() - start) * 1000), error=error)


def _usage(resp) -> dict:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return {}
    extra = getattr(usage, "model_extra", None) or {}
    cost = extra.get("cost", getattr(usage, "cost", None))
    try:
        cost = float(cost) if cost is not None else None
    except (TypeError, ValueError):
        cost = None
    return {"prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None), "cost": cost}


def normalize(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=1, keepdims=True).clip(min=1e-9)


def as_list(value, of: type | None = None) -> list:
    """A field where a list was expected. Models slip: 7 instead of [7], {...} instead of [{...}]."""
    if value is None or value == "":
        return []
    items = list(value) if isinstance(value, (list, tuple, set)) else [value]
    return [x for x in items if of is None or isinstance(x, of)]


def as_int(value) -> int | None:
    """Ids come back as 7, "7" or "#7"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and (m := re.fullmatch(r"\s*#?(\d+)\s*", value)):
        return int(m.group(1))
    return None


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def make_embedder(cfg: Config, llm: LLM):
    """list[str] -> normalized np.ndarray, or None when vectors are disabled."""
    if cfg.embed_model == "none":
        return None
    return lambda texts: llm.embed(texts, cfg.embed_model)
