#!/usr/bin/env python3
"""Letta runtime adapter for hybrid memory retrieval and staged publish.

This module is used by scripts that emit `skill_result` envelopes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from letta_cache import CACHE_ROOT, is_fresh, load_cache, save_cache

DEFAULT_BASE_URL = "https://api.letta.com"
DEFAULT_TTL_SECONDS = 300
DEFAULT_MAX_ITEMS = 100


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _project_path_hash(project_root: str) -> str:
    return _sha256_text(project_root)[:16] if project_root else ""


def resolve_config(task: dict[str, Any]) -> dict[str, Any]:
    project_root = str(task.get("project_root", "")).strip()
    project_id = str(task.get("project_id", "")).strip() or _project_path_hash(project_root)
    return {
        "enabled": _env_bool("LETTA_RUNTIME_ENABLED", False),
        "base_url": os.environ.get("LETTA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "api_key": os.environ.get("LETTA_API_KEY", "").strip(),
        "agent_id": str(task.get("letta_agent_id", task.get("agent_id", ""))).strip() or os.environ.get("LETTA_AGENT_ID", "").strip(),
        "thread_id": str(task.get("thread_id", "")).strip() or os.environ.get("LETTA_THREAD_ID", "").strip(),
        "project_id": project_id,
        "project_root": project_root,
        "project_path_hash": _project_path_hash(project_root),
        "ttl_seconds": max(1, _safe_int(os.environ.get("LETTA_SYNC_TTL_SECONDS", DEFAULT_TTL_SECONDS), DEFAULT_TTL_SECONDS)),
        "max_items": max(1, _safe_int(os.environ.get("LETTA_MAX_ITEMS_PER_SYNC", DEFAULT_MAX_ITEMS), DEFAULT_MAX_ITEMS)),
        "cache_root": Path(os.environ.get("LETTA_CACHE_ROOT", str(CACHE_ROOT))),
        "simulate": os.environ.get("LETTA_SIMULATE", "").strip().lower(),
        "simulate_items": os.environ.get("LETTA_SIMULATE_ITEMS", "").strip(),
        "publish_enabled": _env_bool("LETTA_PUBLISH_ENABLED", False),
    }


def _normalise_remote_items(raw: Any, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    now = int(time.time())
    items: list[dict[str, Any]] = []
    for item in raw[: cfg["max_items"]]:
        if not isinstance(item, dict):
            continue
        folder_id = str(item.get("folder_id", item.get("folder", "default")))
        document_id = str(item.get("document_id", item.get("id", ""))).strip()
        if not document_id:
            continue
        summary = str(item.get("summary", item.get("text", item.get("title", ""))))
        source_uri = str(item.get("source_uri", f"letta://{folder_id}/{document_id}"))
        content_hash = str(item.get("content_hash", _sha256_text(json.dumps(item, sort_keys=True, default=str))))
        meta_project_id = str(item.get("project_id", item.get("project", cfg["project_id"])))
        meta_thread_id = str(item.get("thread_id", item.get("thread", cfg["thread_id"])))
        pointer = {
            "provider": "letta",
            "folder_id": folder_id,
            "document_id": document_id,
            "source_uri": source_uri,
            "content_hash": content_hash,
            "synced_at_unix": int(item.get("synced_at_unix", now)),
            "provenance_tag": str(item.get("provenance_tag", "real")),
            "namespace": str(item.get("namespace", f"ctx://agent/{cfg['agent_id']}")),
            "retrieval_hint": summary[:160],
            "project_id": meta_project_id,
            "project_path_hash": str(item.get("project_path_hash", cfg["project_path_hash"])),
            "thread_id": meta_thread_id,
        }
        items.append({"pointer": pointer, "text": summary})
    return items


def _simulated_items(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items: Any
    if cfg.get("simulate_items"):
        try:
            raw_items = json.loads(str(cfg["simulate_items"]))
        except Exception:
            raw_items = []
    else:
        raw_items = [
            {
                "folder_id": "sim",
                "document_id": "sim-doc-1",
                "summary": "project memory baseline for hybrid retrieval",
                "project_id": cfg["project_id"],
                "thread_id": cfg["thread_id"],
            },
            {
                "folder_id": "sim",
                "document_id": "sim-doc-2",
                "summary": "general fallback memory item",
                "project_id": "other-project",
                "thread_id": "",
            },
        ]
    return _normalise_remote_items(raw_items, cfg)


def _fetch_remote_items(cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    if cfg["simulate"] == "fail":
        return [], ["integration_degraded/letta_sync_failed"]
    if cfg["simulate"] in {"ok", "stale"}:
        items = _simulated_items(cfg)
        if cfg["simulate"] == "stale":
            for row in items:
                row["pointer"]["synced_at_unix"] = 0
                row["pointer"]["stale"] = True
        return items, []
    if not cfg["api_key"]:
        return [], ["validation_failed/letta_sync_missing"]

    url = f"{cfg['base_url']}/v1/agents/{urllib.parse.quote(cfg['agent_id'])}/memory?limit={cfg['max_items']}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {cfg['api_key']}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            payload = json.loads(res.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return [], ["integration_degraded/letta_sync_failed"]

    rows = payload.get("items", payload.get("memory", payload.get("data", []))) if isinstance(payload, dict) else []
    return _normalise_remote_items(rows, cfg), []


def preflight_sync(task: dict[str, Any]) -> dict[str, Any]:
    cfg = resolve_config(task)
    result = {
        "enabled": bool(cfg["enabled"]),
        "agent_id": cfg["agent_id"],
        "sync_status": "skipped",
        "cache_hit": False,
        "items_considered": 0,
        "items": [],
        "reason_codes": [],
        "cache_path": "",
        "project_id": cfg["project_id"],
        "project_path_hash": cfg["project_path_hash"],
        "thread_id": cfg["thread_id"],
    }
    if not cfg["enabled"]:
        return result
    if not cfg["agent_id"]:
        result["sync_status"] = "degraded"
        result["reason_codes"] = ["validation_failed/letta_agent_missing"]
        return result

    cached = load_cache(cfg["agent_id"], cfg["cache_root"])
    cache_items = cached.get("items", []) if isinstance(cached.get("items", []), list) else []
    cache_synced = cached.get("synced_at_unix")

    if is_fresh(cache_synced, cfg["ttl_seconds"]):
        result.update(
            {
                "sync_status": "ok",
                "cache_hit": True,
                "items_considered": len(cache_items),
                "items": cache_items,
                "cache_path": str((cfg["cache_root"] / cfg["agent_id"] / "index.json")),
            }
        )
        return result

    fetched_items, fetch_codes = _fetch_remote_items(cfg)
    if fetch_codes:
        result["reason_codes"] = fetch_codes
        if cache_items:
            result.update(
                {
                    "sync_status": "degraded",
                    "cache_hit": True,
                    "items_considered": len(cache_items),
                    "items": cache_items,
                    "cache_path": str((cfg["cache_root"] / cfg["agent_id"] / "index.json")),
                }
            )
        else:
            result["sync_status"] = "degraded"
        return result

    now = int(time.time())
    cache_payload = {
        "agent_id": cfg["agent_id"],
        "project_id": cfg["project_id"],
        "thread_id": cfg["thread_id"],
        "synced_at_unix": now,
        "items": fetched_items,
    }
    cache_path = save_cache(cfg["agent_id"], cache_payload, cfg["cache_root"])
    result.update(
        {
            "sync_status": "ok",
            "cache_hit": False,
            "items_considered": len(fetched_items),
            "items": fetched_items,
            "cache_path": str(cache_path),
        }
    )
    if any(item.get("pointer", {}).get("stale") for item in fetched_items):
        result["sync_status"] = "degraded"
        result["reason_codes"] = ["integration_degraded/letta_stale"]
    return result


def rank_items(sync_result: dict[str, Any], query_tokens: set[str], top_k: int) -> list[dict[str, Any]]:
    project_id = str(sync_result.get("project_id", ""))
    project_hash = str(sync_result.get("project_path_hash", ""))
    thread_id = str(sync_result.get("thread_id", ""))
    rows = sync_result.get("items", []) if isinstance(sync_result.get("items", []), list) else []

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pointer = row.get("pointer", {}) if isinstance(row.get("pointer", {}), dict) else {}
        text = f"{row.get('text', '')} {pointer.get('retrieval_hint', '')}".lower()
        tokens = {t for t in text.split() if t}
        overlap = len(query_tokens.intersection(tokens))
        score = float(overlap)
        if pointer.get("project_id") == project_id:
            score += 2.0
        if pointer.get("project_path_hash") == project_hash and project_hash:
            score += 1.0
        if thread_id and pointer.get("thread_id") == thread_id:
            score += 1.0
        scored.append((score, {"score": score, "pointer": pointer, "text": row.get("text", "")}))

    scored.sort(key=lambda item: (-item[0], str(item[1].get("pointer", {}).get("document_id", ""))))
    return [row for _, row in scored[: max(1, top_k)]]


def publish_drafts(input_payload: dict[str, Any]) -> dict[str, Any]:
    cfg = resolve_config(input_payload)
    run_id = str(input_payload.get("run_id", ""))
    drafts = input_payload.get("drafts", []) if isinstance(input_payload.get("drafts", []), list) else []
    pointers: list[dict[str, Any]] = []

    preflight_errors: list[str] = []
    if not run_id:
        preflight_errors.append("validation_failed/letta_publish_without_gate")
    if not bool(input_payload.get("validator_passed", False)):
        preflight_errors.append("validation_failed/letta_publish_without_gate")
    if not bool(input_payload.get("governor_approved", False)):
        preflight_errors.append("policy_violation/letta_publish_without_governor")
    if not cfg["agent_id"]:
        preflight_errors.append("validation_failed/letta_agent_missing")
    if preflight_errors:
        return {"ok": False, "reason_codes": sorted(set(preflight_errors)), "external_context_pointers": []}

    now = int(time.time())
    for index, draft in enumerate(drafts, start=1):
        if not isinstance(draft, dict):
            continue
        summary = str(draft.get("summary", draft.get("text", "")))
        source_uri = f"letta://draft/{cfg['agent_id']}/{run_id}/{index}"
        pointer = {
            "provider": "letta",
            "folder_id": str(draft.get("folder_id", cfg["project_id"] or "drafts")),
            "document_id": str(draft.get("document_id", f"{run_id}-{index}")),
            "source_uri": source_uri,
            "content_hash": _sha256_text(summary or source_uri),
            "synced_at_unix": now,
            "provenance_tag": str(draft.get("provenance_tag", "real")),
            "namespace": f"ctx://agent/{cfg['agent_id']}",
            "retrieval_hint": summary[:160],
            "project_id": str(draft.get("project_id", cfg["project_id"])),
            "project_path_hash": cfg["project_path_hash"],
            "thread_id": str(draft.get("thread_id", cfg["thread_id"])),
        }
        pointers.append(pointer)

    return {"ok": True, "reason_codes": [], "external_context_pointers": pointers, "published_count": len(pointers)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sync", "publish"], required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be object")

    if args.mode == "sync":
        result = preflight_sync(payload)
    else:
        result = publish_drafts(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
