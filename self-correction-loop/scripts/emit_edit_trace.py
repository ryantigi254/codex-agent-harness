#!/usr/bin/env python3
"""Emit a deterministic edit_trace artefact for bounded self-correction passes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def _hash_text(value: Any) -> str:
    text = str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    packet = _read_json(args.input)
    pass_index = int(packet.get("pass_index", 0))
    max_passes = int(packet.get("max_passes", 4))

    before_value = packet.get("before", "")
    after_value = packet.get("after", "")
    before_hash = str(packet.get("before_hash", "")) or _hash_text(before_value)
    after_hash = str(packet.get("after_hash", "")) or _hash_text(after_value)

    score_before = float(packet.get("score_before", 0.0))
    score_after = float(packet.get("score_after", 0.0))
    delta = float(packet.get("validator_delta", score_after - score_before))
    stop_reason = str(packet.get("stop_reason", "continue"))

    failure_codes: list[str] = []
    previous_hashes = [str(item) for item in packet.get("previous_hashes", []) if isinstance(item, str)]

    if stop_reason == "continue" and delta <= 0.0:
        failure_codes.append("validation_failed/edit_pass_non_improving")
    if stop_reason == "continue" and pass_index >= max_passes:
        failure_codes.append("validation_failed/edit_loop_exceeded_budget")
    if stop_reason == "continue" and after_hash in previous_hashes:
        failure_codes.append("validation_failed/edit_oscillation_detected")

    edit_trace = {
        "pass_index": pass_index,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "validator_delta": {
            "delta": delta,
            "score_before": score_before,
            "score_after": score_after,
            "validator_id": str(packet.get("validator_id", "validation-gate-runner")),
        },
        "stop_reason": stop_reason,
    }

    ok = len(failure_codes) == 0
    payload = {
        "ok": ok,
        "edit_trace": edit_trace,
        "skill_result": {
            "ok": ok,
            "outputs": {"edit_trace_path": str(args.output)},
            "tool_calls": [{"tool_name": "emit_edit_trace", "params_hash": before_hash, "duration_ms": 0.0}],
            "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
            "artefact_delta": {
                "files_changed": [str(args.output)],
                "files_created": [str(args.output)],
                "tests_run": [],
                "urls_fetched": [],
                "screenshots": [],
            },
            "progress_proxy": {"pass_index": pass_index, "validator_delta": delta},
            "failure_codes": failure_codes,
            "suggested_next": [] if ok else ["self-correction-loop"],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
