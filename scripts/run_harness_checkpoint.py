#!/usr/bin/env python3
"""Compute deterministic harness sufficiency go/no-go from task scorecards."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK_PACK = ROOT / "runbooks/checks/harness_sufficiency/task_pack_v1.json"
DEFAULT_SCORECARDS_DIR = ROOT / "runbooks/checks/harness_sufficiency/scorecards"
DEFAULT_CHECKPOINTS_DIR = ROOT / "runbooks/checks/harness_sufficiency/checkpoints"

TASK_CLASSES = ["research_pdf", "repo_change", "deploy_flow", "long_form_factual"]
STABILITY_KEYS = [
    "contracts_enforced",
    "write_authority_safe",
    "routing_predictable",
    "debuggable_under_10m",
    "cost_variance_bounded",
    "learning_reversible",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def coefficient_of_variation(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance) / mean


def validate_task_pack(task_pack: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tasks = task_pack.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 20:
        errors.append("task_pack:must_have_exactly_20_tasks")
        return errors

    counts = {k: 0 for k in TASK_CLASSES}
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"task_pack:task_{idx}:object_required")
            continue
        for key in (
            "task_id",
            "task_class",
            "prompt_template",
            "required_artefacts",
            "expected_gate_path",
            "max_fanout",
            "max_runtime_hint_min",
        ):
            if key not in task:
                errors.append(f"task_pack:task_{idx}:missing:{key}")
        task_class = task.get("task_class")
        if task_class in counts:
            counts[task_class] += 1
        else:
            errors.append(f"task_pack:task_{idx}:invalid_task_class")

    for klass, count in counts.items():
        if count != 5:
            errors.append(f"task_pack:class_count_invalid:{klass}:{count}")
    return errors


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
            errors.append(f"scorecard:missing:{key}")

    if scorecard.get("task_class") not in TASK_CLASSES:
        errors.append("scorecard:invalid_task_class")

    checks = scorecard.get("stability_checks")
    if not isinstance(checks, dict):
        errors.append("scorecard:stability_checks_object_required")
    else:
        for key in STABILITY_KEYS:
            if key not in checks:
                errors.append(f"scorecard:stability_check_missing:{key}")
            elif not isinstance(checks.get(key), bool):
                errors.append(f"scorecard:stability_check_bool_required:{key}")

    refs = scorecard.get("artefact_refs")
    if not isinstance(refs, dict):
        errors.append("scorecard:artefact_refs_object_required")
    else:
        for key in ("skill_result_ref", "validator_result_ref", "experience_packet_ref"):
            if key not in refs:
                errors.append(f"scorecard:artefact_ref_missing:{key}")

    return errors


def compute_checkpoint(task_pack: dict[str, Any], scorecards: list[dict[str, Any]], checkpoint_id: str, window_start: int, window_end: int, task_pack_ref: str) -> dict[str, Any]:
    class_counts = {k: 0 for k in TASK_CLASSES}
    cost_samples = {k: [] for k in TASK_CLASSES}
    plumbing_change_runs = 0
    stability_aggregate = {k: True for k in STABILITY_KEYS}
    evidence_ok = 0
    routing_ok = 0
    run_ids: list[str] = []

    for score in scorecards:
        run_ids.append(str(score.get("run_id")))
        klass = score.get("task_class")
        if klass in class_counts:
            class_counts[klass] += 1
        checks = score.get("stability_checks", {})
        if isinstance(checks, dict):
            for k in STABILITY_KEYS:
                stability_aggregate[k] = bool(stability_aggregate[k]) and bool(checks.get(k, False))
            if bool(checks.get("contracts_enforced", False)):
                evidence_ok += 1
            if bool(checks.get("routing_predictable", False)):
                routing_ok += 1
            # Use a deterministic proxy cost sample: number of failure codes + 1.
            cost_samples[klass].append(float(len(score.get("failure_mode_codes", [])) + 1))

        if bool(score.get("harness_plumbing_change_required", False)):
            plumbing_change_runs += 1

    total_runs = len(scorecards)
    plumbing_rate = (plumbing_change_runs / total_runs) if total_runs else 0.0
    evidence_coverage_ratio = (evidence_ok / total_runs) if total_runs else 0.0
    routing_consistency_ratio = (routing_ok / total_runs) if total_runs else 0.0

    cost_variance_by_class = {k: round(coefficient_of_variation(cost_samples[k]), 4) for k in TASK_CLASSES}

    failed_conditions: list[str] = []
    if total_runs != 20:
        failed_conditions.append("total_runs_must_equal_20")
    if plumbing_change_runs > 3:
        failed_conditions.append("plumbing_changes_exceeded")
    for klass, cnt in class_counts.items():
        if cnt != 5:
            failed_conditions.append(f"class_distribution_invalid:{klass}")

    for k, passed in stability_aggregate.items():
        if not passed:
            failed_conditions.append(f"stability_failed:{k}")

    for klass, cv in cost_variance_by_class.items():
        if cv > 0.50:
            failed_conditions.append(f"cost_variance_hard_fail:{klass}")

    status = "go" if not failed_conditions else "no_go"
    recommended_actions = [] if status == "go" else [
        "Investigate failed conditions and map to recurring measurable failure modes.",
        "Prefer skill/runbook/eval changes before harness plumbing unless recurrence is proven.",
    ]

    return {
        "checkpoint_id": checkpoint_id,
        "window_start": window_start,
        "window_end": window_end,
        "task_pack_ref": task_pack_ref,
        "runs": run_ids,
        "summary": {
            "total_runs": total_runs,
            "harness_plumbing_change_runs": plumbing_change_runs,
            "harness_plumbing_change_rate": round(plumbing_rate, 4),
            "stability_criteria_pass_map": stability_aggregate,
            "evidence_coverage_ratio": round(evidence_coverage_ratio, 4),
            "routing_consistency_ratio": round(routing_consistency_ratio, 4),
            "cost_variance_by_class": cost_variance_by_class,
        },
        "go_no_go": {
            "status": status,
            "failed_conditions": failed_conditions,
            "recommended_actions": recommended_actions,
        },
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task-pack", default=str(DEFAULT_TASK_PACK))
    p.add_argument("--scorecards-dir", default=str(DEFAULT_SCORECARDS_DIR))
    p.add_argument("--out")
    p.add_argument("--checkpoint-id", default="cp-local")
    p.add_argument("--window-start", type=int, default=0)
    p.add_argument("--window-end", type=int, default=0)
    p.add_argument("--dry-run-fixtures", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    task_pack_path = Path(args.task_pack)
    task_pack = load_json(task_pack_path)
    task_pack_errors = validate_task_pack(task_pack)
    if task_pack_errors:
        print("[FAIL] task pack errors:")
        for err in task_pack_errors:
            print(f"- {err}")
        return 2

    if args.dry_run_fixtures:
        scorecards = [
            load_json(ROOT / "examples/contracts/pass/harness_task_scorecard.json") ["payload"] for _ in range(20)
        ]
        for idx, score in enumerate(scorecards):
            score["run_id"] = f"dry-{idx+1:02d}"
            score["task_id"] = task_pack["tasks"][idx]["task_id"]
            score["task_class"] = task_pack["tasks"][idx]["task_class"]
        checkpoint = compute_checkpoint(
            task_pack=task_pack,
            scorecards=scorecards,
            checkpoint_id="cp-dry-run",
            window_start=0,
            window_end=0,
            task_pack_ref=str(task_pack_path),
        )
        if checkpoint["go_no_go"]["status"] not in {"go", "no_go"}:
            print("[FAIL] invalid checkpoint status in dry run")
            return 2
        print("[PASS] dry-run checkpoint computation succeeded")
        return 0

    scorecards_dir = Path(args.scorecards_dir)
    if not scorecards_dir.exists():
        print(f"[FAIL] scorecards directory missing: {scorecards_dir}")
        return 2

    scorecards: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(scorecards_dir.glob("*.json")):
        payload = load_json(path)
        if isinstance(payload, dict) and "payload" in payload and payload.get("contract") == "harness_task_scorecard":
            payload = payload["payload"]
        if not isinstance(payload, dict):
            errors.append(f"scorecard_file_invalid:{path.name}")
            continue
        s_errors = validate_scorecard(payload)
        if s_errors:
            errors.extend([f"{path.name}:{err}" for err in s_errors])
        else:
            scorecards.append(payload)

    if errors:
        print("[FAIL] scorecard validation errors:")
        for err in errors:
            print(f"- {err}")
        return 2

    checkpoint = compute_checkpoint(
        task_pack=task_pack,
        scorecards=scorecards,
        checkpoint_id=args.checkpoint_id,
        window_start=args.window_start,
        window_end=args.window_end,
        task_pack_ref=str(task_pack_path),
    )

    out_path = Path(args.out) if args.out else (DEFAULT_CHECKPOINTS_DIR / f"{args.checkpoint_id}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(checkpoint, indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] wrote checkpoint: {out_path}")
    print(f"[INFO] status={checkpoint['go_no_go']['status']} failed_conditions={len(checkpoint['go_no_go']['failed_conditions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
