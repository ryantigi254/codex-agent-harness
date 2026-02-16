#!/usr/bin/env python3
"""Emit a memory_design_candidate packet from distillation outputs."""

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
    candidate = {
        "source_run_id": str(packet.get("source_run_id", packet.get("run_id", ""))).strip(),
        "eval_task_ids": _string_list(packet.get("eval_task_ids", packet.get("task_ids", []))),
        "artefact_refs": _string_list(packet.get("artefact_refs", packet.get("evidence_refs", []))),
        "interface_compliant": bool(packet.get("interface_compliant", False)),
        "forbidden_io_detected": bool(packet.get("forbidden_io_detected", False)),
        "score": float(packet.get("score", 0.0)),
        "notes": str(packet.get("notes", "")),
    }

    failure_codes: list[str] = []
    if not candidate["source_run_id"] or not candidate["eval_task_ids"] or not candidate["artefact_refs"]:
        failure_codes.append("schema_violation/memory_design_missing_interface")
    if candidate["forbidden_io_detected"]:
        failure_codes.append("policy_violation/memory_design_forbidden_io")

    ok = len(failure_codes) == 0 and candidate["interface_compliant"]
    if not candidate["interface_compliant"]:
        failure_codes.append("schema_violation/memory_design_missing_interface")

    payload = {
        "ok": ok,
        "memory_design_candidate": candidate,
        "skill_result": {
            "ok": ok,
            "outputs": {"memory_design_candidate_path": str(args.output)},
            "tool_calls": [{"tool_name": "emit_memory_design_candidate", "params_hash": candidate["source_run_id"] or "missing", "duration_ms": 0.0}],
            "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
            "artefact_delta": {
                "files_changed": [str(args.output)],
                "files_created": [str(args.output)],
                "tests_run": [],
                "urls_fetched": [],
                "screenshots": [],
            },
            "progress_proxy": {"eval_task_count": len(candidate["eval_task_ids"]), "score": candidate["score"]},
            "failure_codes": list(dict.fromkeys(failure_codes)),
            "suggested_next": [] if ok else ["experience-to-skill-distiller"],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
