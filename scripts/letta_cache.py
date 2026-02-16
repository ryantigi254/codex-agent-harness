#!/usr/bin/env python3
"""Local cache utilities for Letta runtime integration.

Note: this helper is consumed by scripts that emit `skill_result` envelopes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

CACHE_ROOT = Path("/Users/ryangichuru/.codex/skills/.cache/letta")


def cache_dir(agent_id: str, cache_root: Path | None = None) -> Path:
    root = cache_root or CACHE_ROOT
    return root / agent_id


def cache_index_path(agent_id: str, cache_root: Path | None = None) -> Path:
    return cache_dir(agent_id, cache_root) / "index.json"


def load_cache(agent_id: str, cache_root: Path | None = None) -> dict[str, Any]:
    path = cache_index_path(agent_id, cache_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_cache(agent_id: str, payload: dict[str, Any], cache_root: Path | None = None) -> Path:
    path = cache_index_path(agent_id, cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def is_fresh(synced_at_unix: int | float | None, ttl_seconds: int) -> bool:
    if not isinstance(synced_at_unix, (int, float)):
        return False
    return (time.time() - float(synced_at_unix)) <= float(max(1, ttl_seconds))
