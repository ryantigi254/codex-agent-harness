#!/usr/bin/env python3
"""Emit a debate_trace artefact for critique/debate runs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    packet = _read_json(args.input)
    trace = {
        "speaker_role": str(packet.get("speaker_role", "reviewer")),
        "timestamp": str(packet.get("timestamp", datetime.now(timezone.utc).isoformat())),
        "claim_id": str(packet.get("claim_id", "claim-1")),
        "counterclaim_id": packet.get("counterclaim_id", None),
        "evidence_refs": _string_list(packet.get("evidence_refs", [])),
    }

    failure_codes: list[str] = []
    if not trace["speaker_role"]:
        failure_codes.append("schema_violation/debate_trace_missing_roles")
    if not trace["evidence_refs"]:
        failure_codes.append("validation_failed/debate_claim_missing_evidence_ref")

    ok = len(failure_codes) == 0
    payload = {
        "ok": ok,
        "debate_trace": trace,
        "skill_result": {
            "ok": ok,
            "outputs": {"debate_trace_path": str(args.output)},
            "tool_calls": [{"tool_name": "emit_debate_trace", "params_hash": trace["claim_id"], "duration_ms": 0.0}],
            "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
            "artefact_delta": {
                "files_changed": [str(args.output)],
                "files_created": [str(args.output)],
                "tests_run": [],
                "urls_fetched": [],
                "screenshots": [],
            },
            "progress_proxy": {"evidence_ref_count": len(trace["evidence_refs"])},
            "failure_codes": failure_codes,
            "suggested_next": [] if ok else ["source-grounding-enforcer"],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
