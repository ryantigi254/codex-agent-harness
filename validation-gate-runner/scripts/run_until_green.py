#!/usr/bin/env python3
"""Run validation checks until all pass or fail-closed conditions trigger."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVIDENCE_REQUIRED_FIELDS = {"source", "location", "span", "confidence"}
LETTA_POINTER_REQUIRED_FIELDS = {
    "provider",
    "folder_id",
    "document_id",
    "source_uri",
    "content_hash",
    "synced_at_unix",
    "provenance_tag",
}


def read_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Contract must be a JSON object")
    checks = payload.get("checks", [])
    if not isinstance(checks, list) or not checks:
        raise ValueError("Contract checks must be a non-empty list")
    return payload


def passes(check: dict[str, str], returncode: int, stdout: str) -> bool:
    condition = str(check.get("pass_condition", "exit_code_zero"))
    if condition == "exit_code_zero":
        return returncode == 0
    if condition.startswith("stdout_contains:"):
        token = condition.split(":", 1)[1]
        return token in stdout
    return returncode == 0


def run_check(check: dict[str, str]) -> tuple[bool, dict[str, Any]]:
    command = check["command"]
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    ok = passes(check, result.returncode, result.stdout)
    event = {
        "name": check.get("name", ""),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[:800],
        "stderr": result.stderr[:800],
        "passed": ok,
    }
    return ok, event


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def _build_checklist_state(
    checklist_items: list[dict[str, Any]],
    check_pass_map: dict[str, bool],
    iteration: int,
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    state: list[dict[str, Any]] = []
    flips: list[str] = []
    strict_fail_item_ids: list[str] = []
    strict_blocked: list[str] = []
    state_map: dict[str, str] = {}

    for item in checklist_items:
        item_id = str(item.get("item_id", ""))
        depends_on = [str(dep) for dep in item.get("depends_on", [])]
        dep_blocked = [dep for dep in depends_on if state_map.get(dep) != "satisfied"]
        pass_when = str(item.get("pass_when_check", item_id))
        current_status = str(item.get("status", "unsatisfied"))

        if dep_blocked:
            status = "blocked"
        elif check_pass_map.get(pass_when, False):
            status = "satisfied"
        else:
            status = "unsatisfied"

        satisfied_at_step = item.get("satisfied_at_step")
        if status == "satisfied" and satisfied_at_step is None:
            satisfied_at_step = iteration
            flips.append(item_id)
        if status != "satisfied":
            satisfied_at_step = None

        if item.get("strictness") == "strict" and status == "unsatisfied":
            strict_fail_item_ids.append(item_id)
        if item.get("strictness") == "strict" and status == "blocked":
            strict_blocked.append(item_id)

        row = dict(item)
        row["status"] = status
        row["satisfied_at_step"] = satisfied_at_step
        state.append(row)
        state_map[item_id] = status

    return state, flips, strict_fail_item_ids, strict_blocked


def _validate_evidence_objects(raw: Any) -> list[str]:
    reason_codes: list[str] = []
    if not isinstance(raw, list):
        return reason_codes
    for item in raw:
        if not isinstance(item, dict):
            reason_codes.append("schema_violation/evidence_object_invalid_type")
            continue
        for key in EVIDENCE_REQUIRED_FIELDS:
            if key not in item:
                reason_codes.append("schema_violation/evidence_object_missing_required")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)):
            reason_codes.append("schema_violation/evidence_object_invalid_type")
        elif float(confidence) < 0.0 or float(confidence) > 1.0:
            reason_codes.append("validation_failed/evidence_confidence_out_of_range")
        if "location" in item and not isinstance(item.get("location"), dict):
            reason_codes.append("schema_violation/evidence_object_invalid_type")
    return _dedupe(reason_codes)


def _validate_letta_pointers(raw: Any) -> list[str]:
    reason_codes: list[str] = []
    if raw is None:
        return reason_codes
    if not isinstance(raw, list):
        return ["schema_violation/letta_pointer_invalid_type"]
    for item in raw:
        if not isinstance(item, dict):
            reason_codes.append("schema_violation/letta_pointer_invalid_type")
            continue
        for key in LETTA_POINTER_REQUIRED_FIELDS:
            if key not in item:
                reason_codes.append("schema_violation/letta_pointer_missing_required")
        if item.get("provider") not in (None, "letta"):
            reason_codes.append("schema_violation/letta_pointer_invalid_type")
        if not str(item.get("content_hash", "")).strip():
            reason_codes.append("validation_failed/letta_pointer_hash_missing")
        synced_at = item.get("synced_at_unix")
        if not isinstance(synced_at, (int, float)):
            reason_codes.append("schema_violation/letta_pointer_invalid_type")
        elif float(synced_at) <= 0:
            reason_codes.append("validation_failed/letta_pointer_stale_sync")
        if item.get("stale", False) is True or item.get("is_stale", False) is True:
            reason_codes.append("validation_failed/letta_pointer_stale_sync")
    return _dedupe(reason_codes)


def _validate_correction_rollout(raw: Any) -> list[str]:
    reason_codes: list[str] = []
    if raw is None:
        return reason_codes
    if not isinstance(raw, dict):
        return ["schema_violation/correction_rollout_missing_required"]
    required = ("run_id", "task_signature", "attempt_1", "attempt_2")
    for key in required:
        if not str(raw.get(key, "")).strip():
            reason_codes.append("schema_violation/correction_rollout_missing_required")
    if "attempt_2" in raw and not str(raw.get("attempt_2", "")).strip():
        reason_codes.append("validation_failed/self_correction_missing_o2")
    if "task_signature" in raw and not isinstance(raw.get("task_signature"), str):
        reason_codes.append("schema_violation/correction_rollout_mismatched_task_signature")
    return _dedupe(reason_codes)


def main() -> int:
    args = parse_args()
    contract = read_contract(args.contract)
    max_iterations = int(contract.get("max_iterations", 5))
    checks: list[dict[str, str]] = contract["checks"]
    memory_bundle = contract.get("memory_update_bundle", {}) if isinstance(contract.get("memory_update_bundle", {}), dict) else {}
    execution_audit = contract.get("execution_audit", {}) if isinstance(contract.get("execution_audit", {}), dict) else {}
    strict_evidence = bool(contract.get("strict_evidence_objects", False))
    evidence_objects = contract.get("evidence_objects", contract.get("evidence_refs", []))
    correction_rollout = contract.get("correction_rollout", {})
    if correction_rollout is not None and not isinstance(correction_rollout, dict):
        correction_rollout = {}
    external_context_pointers = contract.get("external_context_pointers", [])
    if not isinstance(external_context_pointers, list):
        external_context_pointers = []
    external_context_policy = contract.get("external_context_policy", {}) if isinstance(contract.get("external_context_policy", {}), dict) else {}
    trust_level = str(contract.get("trust_level", execution_audit.get("trust_level", "trusted")))
    checklist = contract.get("checklist_contract", {}) if isinstance(contract.get("checklist_contract", {}), dict) else {}
    checklist_items: list[dict[str, Any]] = checklist.get("items", []) if isinstance(checklist.get("items", []), list) else []
    letta_runtime_enabled = bool(contract.get("letta_runtime_enabled", False))
    letta_agent_id = str(contract.get("letta_agent_id", "")).strip()
    letta_sync_status = str(contract.get("letta_sync_status", "")).strip().lower()
    letta_publish_attempted = bool(contract.get("letta_publish_attempted", False))
    validator_passed = bool(contract.get("validator_passed", False))
    governor_approved = bool(contract.get("governor_approved", False))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.output_dir / "iteration_log.jsonl"
    checklist_timeline_path = args.output_dir / "checklist_timeline.jsonl"

    all_passed = False
    aborted = False
    strict_early_terminated = False
    iterations = 0
    reason_codes: list[str] = []
    progress_history: list[float] = []
    progress_deltas: list[float] = []
    checklist_deltas: list[dict[str, Any]] = []
    previous_progress: float | None = None
    consecutive_no_progress = 0
    max_consecutive_no_progress = 0
    strategy_switch_tag: str | None = None
    diagnostic_ran = False
    diagnostic_result: dict[str, Any] = {}
    latest_checklist_state: list[dict[str, Any]] = checklist_items
    strict_fail_item_ids: list[str] = []

    with log_path.open("w", encoding="utf-8") as handle, checklist_timeline_path.open("w", encoding="utf-8") as checklist_handle:
        for iteration in range(1, max_iterations + 1):
            iterations = iteration
            iteration_passed = True
            passed_checks = 0
            check_pass_map: dict[str, bool] = {}

            for check in checks:
                passed, event = run_check(check)
                check_name = str(check.get("name", ""))
                check_pass_map[check_name] = passed
                handle.write(
                    json.dumps(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "run_id": args.run_id,
                            "iteration": iteration,
                            **event,
                        }
                    )
                    + "\n"
                )
                if not passed:
                    iteration_passed = False
                else:
                    passed_checks += 1

            progress_score = round(passed_checks / max(1, len(checks)), 6)
            progress_delta_iteration = round(
                progress_score - previous_progress if previous_progress is not None else progress_score,
                6,
            )
            progress_history.append(progress_score)
            progress_deltas.append(progress_delta_iteration)
            no_progress_step = previous_progress is not None and progress_delta_iteration <= 0.0
            if no_progress_step:
                consecutive_no_progress += 1
            else:
                consecutive_no_progress = 0
            max_consecutive_no_progress = max(max_consecutive_no_progress, consecutive_no_progress)
            previous_progress = progress_score

            handle.write(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "run_id": args.run_id,
                        "iteration": iteration,
                        "event": "progress_delta",
                        "progress_score": progress_score,
                        "progress_delta": progress_delta_iteration,
                        "no_progress_step": no_progress_step,
                        "consecutive_no_progress": consecutive_no_progress,
                    }
                )
                + "\n"
            )

            if checklist_items:
                latest_checklist_state, flipped_items, strict_fails, strict_blocked = _build_checklist_state(
                    latest_checklist_state,
                    check_pass_map,
                    iteration,
                )
                strict_fail_item_ids = strict_fails
                checklist_delta = {
                    "iteration": iteration,
                    "flipped_to_satisfied": flipped_items,
                    "strict_fail_item_ids": strict_fails,
                    "strict_blocked_item_ids": strict_blocked,
                }
                checklist_deltas.append(checklist_delta)
                checklist_handle.write(
                    json.dumps(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "run_id": args.run_id,
                            "iteration": iteration,
                            "checklist_state": latest_checklist_state,
                            "checklist_delta": checklist_delta,
                        },
                        ensure_ascii=True,
                    )
                    + "\n"
                )

                if strict_fails:
                    strict_early_terminated = True
                    aborted = True
                    reason_codes.append("validation_failed/checklist_strict_failed")
                    reason_codes.append("evidence_missing/checklist_evidence_missing")
                    break

            if iteration_passed:
                all_passed = True
                break

            if consecutive_no_progress >= 2:
                strategy_switch_tag = "stalled_no_progress"
                reason_codes.append("no_progress/no_progress_loop")
                handle.write(
                    json.dumps(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "run_id": args.run_id,
                            "iteration": iteration,
                            "event": "strategy_switch",
                            "strategy_switch_tag": strategy_switch_tag,
                            "policy": "switch_then_diagnose_then_abort_if_flat",
                        }
                    )
                    + "\n"
                )

                diagnostic_ran = True
                diagnostic_passed = 0
                for check in checks:
                    passed, event = run_check(check)
                    if passed:
                        diagnostic_passed += 1
                    handle.write(
                        json.dumps(
                            {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "run_id": args.run_id,
                                "iteration": iteration,
                                "event": "diagnostic_check",
                                **event,
                            }
                        )
                        + "\n"
                    )

                diagnostic_progress = round(diagnostic_passed / max(1, len(checks)), 6)
                diagnostic_delta = round(diagnostic_progress - progress_score, 6)
                diagnostic_result = {
                    "diagnostic_progress": diagnostic_progress,
                    "diagnostic_delta": diagnostic_delta,
                    "diagnostic_passed_checks": diagnostic_passed,
                }
                handle.write(
                    json.dumps(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "run_id": args.run_id,
                            "iteration": iteration,
                            "event": "diagnostic_result",
                            **diagnostic_result,
                        }
                    )
                    + "\n"
                )

                if diagnostic_delta <= 0.0:
                    aborted = True
                    reason_codes.append("validation_failed/diagnostic_no_improvement")
                    break

                previous_progress = diagnostic_progress
                progress_history.append(diagnostic_progress)
                progress_deltas.append(diagnostic_delta)
                consecutive_no_progress = 0

    if not all_passed:
        reason_codes.append("validation_failed/checks_failed")
        if aborted:
            reason_codes.append("validation_failed/fail_closed_abort")
        if iterations >= max_iterations and not aborted:
            reason_codes.append("validation_failed/max_iterations_reached")

    if memory_bundle:
        if not memory_bundle.get("evidence_refs"):
            reason_codes.append("validation_failed/memory_provenance_missing")
        if not memory_bundle.get("commit_message"):
            reason_codes.append("validation_failed/memory_commit_missing")
        if not memory_bundle.get("worktree_path"):
            reason_codes.append("validation_failed/worktree_required_for_memory_write")
        if bool(memory_bundle.get("defrag_run", False)) and not memory_bundle.get("relocation_pointers"):
            reason_codes.append("validation_failed/defrag_relocation_missing")
    if strict_evidence:
        reason_codes.extend(_validate_evidence_objects(evidence_objects))
    if correction_rollout:
        reason_codes.extend(_validate_correction_rollout(correction_rollout))
        score_o1 = correction_rollout.get("validator_score_o1")
        score_o2 = correction_rollout.get("validator_score_o2")
        if not isinstance(score_o1, (int, float)) or not isinstance(score_o2, (int, float)):
            reason_codes.append("validation_failed/self_correction_unscored")
        elif float(score_o1) >= 1.0 and float(score_o2) < 1.0:
            reason_codes.append("validation_failed/self_correction_regressed")
    if letta_runtime_enabled and not letta_agent_id:
        reason_codes.append("validation_failed/letta_agent_missing")
    if letta_runtime_enabled and not letta_sync_status:
        reason_codes.append("validation_failed/letta_sync_missing")
    if letta_runtime_enabled and letta_sync_status == "degraded":
        reason_codes.append("integration_degraded/letta_sync_failed")
    if bool(contract.get("letta_sync_stale", False)):
        reason_codes.append("integration_degraded/letta_stale")
    if letta_publish_attempted and not validator_passed:
        reason_codes.append("validation_failed/letta_publish_without_gate")
    if letta_publish_attempted and not governor_approved:
        reason_codes.append("policy_violation/letta_publish_without_governor")
    if external_context_pointers:
        reason_codes.extend(_validate_letta_pointers(external_context_pointers))
    direct_external_write = bool(
        contract.get("direct_external_memory_write", False)
        or contract.get("external_memory_write_committed", False)
        or memory_bundle.get("direct_external_memory_write", False)
        or memory_bundle.get("external_write_committed", False)
    )
    if external_context_policy.get("direct_external_writes_forbidden", True) and direct_external_write:
        reason_codes.append("policy_violation/letta_direct_memory_write_forbidden")
    if trust_level in {"untrusted", "generated_untrusted"}:
        if not str(execution_audit.get("execution_profile", contract.get("requested_profile", ""))).strip():
            reason_codes.append("validation_failed/missing_execution_profile")
        if not str(execution_audit.get("audit_ref", contract.get("audit_ref", ""))).strip():
            reason_codes.append("validation_failed/missing_execution_audit_ref")

    initial_progress = progress_history[0] if progress_history else 0.0
    final_progress = progress_history[-1] if progress_history else 0.0
    best_progress = max(progress_history) if progress_history else 0.0
    net_delta = round(final_progress - initial_progress, 6)
    mean_delta = round(sum(progress_deltas) / len(progress_deltas), 6) if progress_deltas else 0.0
    checklist_flip_count = sum(len(row.get("flipped_to_satisfied", [])) for row in checklist_deltas)
    aggregate_progress = round((0.7 * net_delta) + (0.3 * checklist_flip_count / max(1, len(checklist_items))), 6)

    if net_delta > 0.001:
        trend = "up"
    elif net_delta < -0.001:
        trend = "down"
    else:
        trend = "flat"

    reason_codes = _dedupe(reason_codes)
    if reason_codes:
        all_passed = False
    summary = {
        "run_id": args.run_id,
        "all_passed": all_passed,
        "aborted": aborted,
        "iterations": iterations,
        "log_path": str(log_path),
        "checklist_timeline_ref": str(checklist_timeline_path),
        "checklist_state": latest_checklist_state,
        "checklist_deltas": checklist_deltas,
        "strict_fail_item_ids": strict_fail_item_ids,
        "strict_early_terminated": strict_early_terminated,
        "gate_scores": {
            "all_checks_passed": {"passed": all_passed, "weight": 0.5},
            "checklist_satisfied": {
                "passed": all(item.get("status") == "satisfied" for item in latest_checklist_state) if latest_checklist_state else True,
                "weight": 0.3,
            },
            "budget_respected": {"passed": iterations <= max_iterations, "weight": 0.1},
            "no_progress_policy_respected": {"passed": not (diagnostic_ran and not aborted), "weight": 0.1},
        },
        "progress_delta": net_delta,
        "progress_delta_aggregate": aggregate_progress,
        "progress_trend": trend,
        "progress_summary": {
            "initial": round(initial_progress, 6),
            "final": round(final_progress, 6),
            "best": round(best_progress, 6),
            "net_delta": net_delta,
            "mean_delta": mean_delta,
            "history": [round(item, 6) for item in progress_history],
            "checklist_flip_count": checklist_flip_count,
        },
        "reason_codes": reason_codes,
        "strategy_switch_tag": strategy_switch_tag,
        "diagnostic_ran": diagnostic_ran,
        "diagnostic_result": diagnostic_result,
        "execution_audit": execution_audit,
        "strict_evidence_objects": strict_evidence,
        "correction_rollout": correction_rollout if correction_rollout else {},
        "self_correction_scores": {
            "validator_score_o1": correction_rollout.get("validator_score_o1") if correction_rollout else None,
            "validator_score_o2": correction_rollout.get("validator_score_o2") if correction_rollout else None,
            "improvement_delta": correction_rollout.get("improvement_delta") if correction_rollout else None,
        },
        "no_progress_counters": {
            "max_consecutive_no_progress": max_consecutive_no_progress,
            "trigger_threshold": 2,
        },
    }

    summary_outputs = dict(summary)
    summary["skill_result"] = {
        "ok": all_passed,
        "outputs": summary_outputs,
        "tool_calls": [{"tool_name": "run_until_green", "params_hash": args.run_id, "duration_ms": 0.0}],
        "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
        "artefact_delta": {
            "files_changed": [str(log_path), str(checklist_timeline_path)],
            "tests_run": [check["name"] for check in checks],
            "urls_fetched": [],
        },
        "progress_proxy": {
            "iterations": iterations,
            "all_passed": all_passed,
            "progress_trend": trend,
            "checklist_flip_count": checklist_flip_count,
        },
        "failure_codes": reason_codes,
        "suggested_next": [] if all_passed else ["inspect_iteration_log", "switch_strategy"],
        "gate_scores": summary["gate_scores"],
        "progress_delta": summary["progress_delta_aggregate"],
        "reason_codes": reason_codes,
        "loop_flags": {
            "consecutive_no_progress_threshold": 2,
            "diagnostic_ran": diagnostic_ran,
            "aborted_after_diagnostic": aborted,
            "strict_early_terminated": strict_early_terminated,
        },
        "checklist_state": summary["checklist_state"],
        "checklist_deltas": summary["checklist_deltas"],
    }

    print(json.dumps(summary, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
