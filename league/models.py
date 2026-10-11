"""Calling managers. Real calls go through OpenRouter; --mock returns random valid books."""
from __future__ import annotations

import json
import os
import random
import re
import time

import requests

from . import config

SCHEMA = {
    "name": "fund_rebalance",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["weights", "thesis", "note"],
        "properties": {
            "weights": {"type": "object", "additionalProperties": False,
                        "required": config.TRADABLE + ["CASH"],
                        "properties": {k: {"type": "number"} for k in config.TRADABLE + ["CASH"]}},
            "thesis": {"type": "string"},
            "note": {"type": "string"},
        },
    },
}


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in reply")
    return json.loads(m.group(0))


def ask_openrouter(model: str, system: str, user: str, tries: int = 3) -> tuple[dict, dict]:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": 4000,
        "reasoning": {"effort": "low"},
        "response_format": {"type": "json_schema", "json_schema": SCHEMA},
        "usage": {"include": True},
    }
    last_err = None
    for attempt in range(tries + 1):   # +1: one free retry after dropping response_format
        try:
            t0 = time.time()
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                       "HTTP-Referer": "https://github.com/itsarcvale/ai-fund-league", "X-Title": "AI Hedge Fund League"},
                              json=body, timeout=180)
            if r.status_code == 400 and "response_format" in body:
                body.pop("response_format")       # model without structured outputs: fall back to plain JSON
                continue
            r.raise_for_status()
            j = r.json()
            text = j["choices"][0]["message"]["content"] or ""
            parsed = _extract_json(text)
            u = j.get("usage") or {}
            usage = {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                     "cost_usd": u.get("cost"), "seconds": round(time.time() - t0, 1), "served_by": j.get("model")}
            return parsed, usage
        except Exception as e:   # noqa: BLE001
            last_err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{model}: {last_err}")


def ask_mock(manager_id: str, week_seed: str) -> tuple[dict, dict]:
    rnd = random.Random(f"{manager_id}-{week_seed}")
    picks = rnd.sample(config.TRADABLE, 4)
    raw = [rnd.random() for _ in picks]
    total = sum(raw) / rnd.uniform(0.6, 1.0)
    w = {k: 0.0 for k in config.TRADABLE}
    for k, v in zip(picks, raw):
        w[k] = round(v / total, 3)
    if rnd.random() < 0.3:
        w[rnd.choice([k for k in config.TRADABLE if k not in picks])] = -0.1
    w["CASH"] = round(1 - sum(w.values()), 3)
    return ({"weights": w, "thesis": f"Mock thesis for {manager_id}.", "note": "Mock decision used for testing the pipeline."},
            {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0, "seconds": 0, "served_by": "mock"})


def clean_weights(raw: dict) -> dict:
    """Enforce league rules. Returns risk weights only; CASH is the remainder."""
    w = {}
    for k in config.TRADABLE:
        try:
            v = float(raw.get(k, 0) or 0)
        except (TypeError, ValueError):
            v = 0.0
        if abs(v) > 1.5:                       # model answered in percent
            v /= 100.0
        w[k] = max(-config.MAX_SINGLE, min(config.MAX_SINGLE, v))
    gross = sum(abs(v) for v in w.values())
    if gross > config.MAX_GROSS:
        w = {k: v * config.MAX_GROSS / gross for k, v in w.items()}
    return {k: round(v, 4) for k, v in w.items() if abs(v) >= 0.0005}
