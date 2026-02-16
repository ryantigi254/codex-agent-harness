#!/usr/bin/env python3
"""Emit a routing_decision_packet for budgeted model-routing decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def _normalise_candidates(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            out.append({"model_id": item})
        elif isinstance(item, dict) and isinstance(item.get("model_id"), str):
            out.append(
                {
                    "model_id": str(item.get("model_id")),
                    "estimated_cost": float(item.get("estimated_cost", 0.0)),
                    "estimated_latency_ms": int(item.get("estimated_latency_ms", 0)),
                }
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    packet = _read_json(args.input)
    candidates = _normalise_candidates(packet.get("candidate_models", []))
    chosen_model = str(packet.get("chosen_model", "")).strip()

    if not chosen_model and candidates:
        chosen_model = str(candidates[0]["model_id"])

    failure_codes: list[str] = []
    if len(candidates) > 1 and (not chosen_model):
        failure_codes.append("schema_violation/routing_packet_missing")
    if chosen_model and candidates and chosen_model not in {row["model_id"] for row in candidates}:
        failure_codes.append("schema_violation/routing_packet_missing")

    confidence = float(packet.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))
    budget_state = packet.get("budget_state", {}) if isinstance(packet.get("budget_state"), dict) else {}

    routing_packet = {
        "step_id": str(packet.get("step_id", "step-1")),
        "candidate_models": candidates,
        "chosen_model": chosen_model,
        "confidence": confidence,
        "budget_state": {
            "remaining_tokens": int(budget_state.get("remaining_tokens", packet.get("remaining_tokens", 0))),
            "remaining_time_ms": int(budget_state.get("remaining_time_ms", packet.get("remaining_time_ms", 0))),
        },
        "justification_code": str(packet.get("justification_code", "budgeted_escalation")),
        "validator_risk": str(packet.get("validator_risk", "medium")),
    }

    ok = len(failure_codes) == 0
    payload = {
        "ok": ok,
        "routing_decision_packet": routing_packet,
        "skill_result": {
            "ok": ok,
            "outputs": {"routing_decision_packet_path": str(args.output)},
            "tool_calls": [{"tool_name": "emit_routing_decision_packet", "params_hash": routing_packet["step_id"], "duration_ms": 0.0}],
            "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
            "artefact_delta": {
                "files_changed": [str(args.output)],
                "files_created": [str(args.output)],
                "tests_run": [],
                "urls_fetched": [],
                "screenshots": [],
            },
            "progress_proxy": {"candidate_count": len(candidates), "confidence": confidence},
            "failure_codes": failure_codes,
            "suggested_next": [] if ok else ["uncertainty-calibrated-answering"],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
