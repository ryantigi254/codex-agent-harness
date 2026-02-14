#!/usr/bin/env python3
"""Create and validate a harness task scorecard from run artefact refs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_STABILITY_KEYS = [
    "contracts_enforced",
    "write_authority_safe",
    "routing_predictable",
    "debuggable_under_10m",
    "cost_variance_bounded",
    "learning_reversible",
]

REQUIRED_ARTEFACT_KEYS = [
    "skill_result_ref",
    "validator_result_ref",
    "experience_packet_ref",
]

TASK_CLASSES = {"research_pdf", "repo_change", "deploy_flow", "long_form_factual"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_scorecard(scorecard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "run_id",
        "task_id",
        "task_class",
        "timestamp_unix",
        "artefact_refs",
        "stability_checks",
        "harness_plumbing_change_required",
        "failure_mode_codes",
        "notes",
    ):
        if key not in scorecard:
            errors.append(f"schema:harness_task_scorecard:missing:{key}")

    task_class = scorecard.get("task_class")
    if task_class not in TASK_CLASSES:
        errors.append("schema:harness_task_scorecard:invalid_task_class")

    artefact_refs = scorecard.get("artefact_refs")
    if not isinstance(artefact_refs, dict):
        errors.append("schema:harness_task_scorecard:artefact_refs_object_required")
    else:
        for key in REQUIRED_ARTEFACT_KEYS:
            if key not in artefact_refs or not isinstance(artefact_refs.get(key), str):
                errors.append(f"schema:harness_task_scorecard:artefact_ref_missing:{key}")

    checks = scorecard.get("stability_checks")
    if not isinstance(checks, dict):
        errors.append("schema:harness_task_scorecard:stability_checks_object_required")
    else:
        for key in REQUIRED_STABILITY_KEYS:
            if key not in checks:
                errors.append(f"schema:harness_task_scorecard:stability_check_missing:{key}")
            elif not isinstance(checks.get(key), bool):
                errors.append(f"schema:harness_task_scorecard:stability_check_bool_required:{key}")

    if not isinstance(scorecard.get("harness_plumbing_change_required"), bool):
        errors.append("schema:harness_task_scorecard:harness_plumbing_change_required_bool")
    if not isinstance(scorecard.get("failure_mode_codes"), list):
        errors.append("schema:harness_task_scorecard:failure_mode_codes_array_required")
    if not isinstance(scorecard.get("notes"), str):
        errors.append("schema:harness_task_scorecard:notes_string_required")

    return errors


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--task-class", required=True, choices=sorted(TASK_CLASSES))
    p.add_argument("--timestamp-unix", type=int, required=True)
    p.add_argument("--skill-result-ref", required=True)
    p.add_argument("--validator-result-ref", required=True)
    p.add_argument("--experience-packet-ref", required=True)
    p.add_argument("--merge-audit-ref")
    p.add_argument("--checkpoint-ref")
    p.add_argument("--harness-plumbing-change-required", action="store_true")
    p.add_argument("--failure-mode-code", action="append", default=[])
    p.add_argument("--notes", default="")
    p.add_argument("--stability-checks-json", required=True, help="JSON object with all six stability keys")
    p.add_argument("--out", required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)

    try:
        stability_checks = json.loads(args.stability_checks_json)
    except json.JSONDecodeError:
        print("[FAIL] --stability-checks-json must be valid JSON object")
        return 2

    scorecard: dict[str, Any] = {
        "run_id": args.run_id,
        "task_id": args.task_id,
        "task_class": args.task_class,
        "timestamp_unix": args.timestamp_unix,
        "artefact_refs": {
            "skill_result_ref": args.skill_result_ref,
            "validator_result_ref": args.validator_result_ref,
            "experience_packet_ref": args.experience_packet_ref,
        },
        "stability_checks": stability_checks,
        "harness_plumbing_change_required": bool(args.harness_plumbing_change_required),
        "failure_mode_codes": args.failure_mode_code,
        "notes": args.notes,
    }
    if args.merge_audit_ref:
        scorecard["artefact_refs"]["merge_audit_ref"] = args.merge_audit_ref
    if args.checkpoint_ref:
        scorecard["artefact_refs"]["checkpoint_ref"] = args.checkpoint_ref

    errors = validate_scorecard(scorecard)
    if errors:
        print("[FAIL] scorecard validation errors:")
        for err in errors:
            print(f"- {err}")
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] wrote scorecard: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
