#!/usr/bin/env python3
"""Compile a validation contract from task JSON input."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CHECKLIST_ALLOWED_STATUS = {"unsatisfied", "satisfied", "blocked"}
CHECKLIST_ALLOWED_STRICTNESS = {"strict", "normal"}
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


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def normalise_checks(raw_checks: Any) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    if not isinstance(raw_checks, list):
        return checks
    for index, item in enumerate(raw_checks):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", f"check-{index+1}")).strip()
        command = str(item.get("command", "")).strip()
        pass_condition = str(item.get("pass_condition", "exit_code_zero")).strip()
        if not command:
            continue
        checks.append({"name": name, "command": command, "pass_condition": pass_condition})
    return checks


def _checklist_cycle(items: list[dict[str, Any]]) -> bool:
    graph: dict[str, list[str]] = {str(item["item_id"]): [str(dep) for dep in item.get("depends_on", [])] for item in items}
    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(node: str) -> bool:
        if node in stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for dep in graph.get(node, []):
            if dep in graph and dfs(dep):
                return True
        stack.remove(node)
        return False

    return any(dfs(node) for node in graph)


def normalise_checklist(raw: Any, run_id: str) -> tuple[dict[str, Any], list[str]]:
    reason_codes: list[str] = []
    if not isinstance(raw, dict):
        return {"run_id": run_id, "items": [], "termination_policy": "strict_gate", "reason_codes": [], "version": "1.0.0"}, reason_codes

    raw_items = raw.get("items", []) if isinstance(raw.get("items", []), list) else []
    items: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            reason_codes.append("schema_violation/checklist_contract_missing_required")
            continue
        item_id = str(item.get("item_id", f"item-{idx:03d}")).strip()
        question = str(item.get("question", "")).strip()
        evidence_required = item.get("evidence_required", []) if isinstance(item.get("evidence_required", []), list) else []
        strictness = str(item.get("strictness", "normal")).strip()
        depends_on = item.get("depends_on", []) if isinstance(item.get("depends_on", []), list) else []
        status = str(item.get("status", "unsatisfied")).strip()
        satisfied_at_step = item.get("satisfied_at_step")
        evidence_refs = item.get("evidence_refs", []) if isinstance(item.get("evidence_refs", []), list) else []
        pass_when_check = str(item.get("pass_when_check", item_id)).strip()

        if not question or not item_id:
            reason_codes.append("schema_violation/checklist_contract_missing_required")
            continue
        if strictness not in CHECKLIST_ALLOWED_STRICTNESS:
            reason_codes.append("schema_violation/checklist_invalid_strictness")
            strictness = "normal"
        if status not in CHECKLIST_ALLOWED_STATUS:
            status = "unsatisfied"

        items.append(
            {
                "item_id": item_id,
                "question": question,
                "evidence_required": [str(v) for v in evidence_required],
                "strictness": strictness,
                "depends_on": [str(v) for v in depends_on],
                "status": status,
                "satisfied_at_step": satisfied_at_step if isinstance(satisfied_at_step, int) or satisfied_at_step is None else None,
                "evidence_refs": [str(v) for v in evidence_refs],
                "pass_when_check": pass_when_check,
            }
        )

    if _checklist_cycle(items):
        reason_codes.append("schema_violation/checklist_dependency_cycle")

    contract = {
        "run_id": run_id,
        "items": items,
        "termination_policy": str(raw.get("termination_policy", "strict_gate")),
        "reason_codes": sorted(set(reason_codes)),
        "version": str(raw.get("version", "1.0.0")),
    }
    return contract, sorted(set(reason_codes))


def _validate_evidence_objects(raw: Any) -> list[str]:
    reason_codes: list[str] = []
    if not isinstance(raw, list):
        return reason_codes
    for item in raw:
        if not isinstance(item, dict):
            reason_codes.append("schema_violation/evidence_object_invalid_type")
            continue
        missing = [key for key in EVIDENCE_REQUIRED_FIELDS if key not in item]
        if missing:
            reason_codes.append("schema_violation/evidence_object_missing_required")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)):
            reason_codes.append("schema_violation/evidence_object_invalid_type")
        elif float(confidence) < 0.0 or float(confidence) > 1.0:
            reason_codes.append("validation_failed/evidence_confidence_out_of_range")
        if "location" in item and not isinstance(item.get("location"), dict):
            reason_codes.append("schema_violation/evidence_object_invalid_type")
    return sorted(set(reason_codes))


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
        missing = [key for key in LETTA_POINTER_REQUIRED_FIELDS if key not in item]
        if missing:
            reason_codes.append("schema_violation/letta_pointer_missing_required")
        provider = item.get("provider")
        if provider is not None and provider != "letta":
            reason_codes.append("schema_violation/letta_pointer_invalid_type")
        if not str(item.get("content_hash", "")).strip():
            reason_codes.append("validation_failed/letta_pointer_hash_missing")
        synced_at = item.get("synced_at_unix")
        if synced_at is None or not isinstance(synced_at, (int, float)):
            reason_codes.append("schema_violation/letta_pointer_invalid_type")
        elif float(synced_at) <= 0:
            reason_codes.append("validation_failed/letta_pointer_stale_sync")
        if item.get("stale", False) is True or item.get("is_stale", False) is True:
            reason_codes.append("validation_failed/letta_pointer_stale_sync")
    return sorted(set(reason_codes))


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
    return sorted(set(reason_codes))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-json", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def _fail_payload(run_id: str, reason_codes: list[str], check_count: int) -> dict[str, Any]:
    return {
        "error": "Validation contract is invalid. Gate fails closed.",
        "reason_codes": reason_codes,
        "skill_result": {
            "ok": False,
            "outputs": {"check_count": check_count},
            "tool_calls": [{"tool_name": "compile_checks", "params_hash": run_id, "duration_ms": 0.0}],
            "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
            "artefact_delta": {"files_changed": [], "tests_run": [], "urls_fetched": []},
            "progress_proxy": {"check_count": check_count},
            "failure_codes": reason_codes,
            "suggested_next": ["repair_validation_contract"],
            "gate_scores": {"checks_present": {"passed": check_count > 0, "weight": 1.0}},
            "progress_delta": 0.0,
            "reason_codes": reason_codes,
        },
    }


def main() -> int:
    args = parse_args()
    task = read_json(args.task_json)
    checks = normalise_checks(task.get("acceptance_tests", []))
    checklist_contract, checklist_reason_codes = normalise_checklist(task.get("checklist_contract", {}), args.run_id)
    memory_bundle = task.get("memory_update_bundle", {}) if isinstance(task.get("memory_update_bundle", {}), dict) else {}
    execution_audit = task.get("execution_audit", {}) if isinstance(task.get("execution_audit", {}), dict) else {}
    evidence_objects = task.get("evidence_objects", task.get("evidence_refs", []))
    external_context_pointers = task.get("external_context_pointers", [])
    if not isinstance(external_context_pointers, list):
        external_context_pointers = []
    memory_required = task.get("task_tag") == "memory_write" or bool(memory_bundle)
    trust_level = str(task.get("trust_level", execution_audit.get("trust_level", "trusted")))
    strict_evidence = bool(task.get("strict_evidence_objects", False))
    external_context_policy = task.get("external_context_policy", {}) if isinstance(task.get("external_context_policy", {}), dict) else {}
    correction_rollout = task.get("correction_rollout", {})
    if correction_rollout is not None and not isinstance(correction_rollout, dict):
        correction_rollout = {}
    letta_runtime_enabled = bool(task.get("letta_runtime_enabled", False))
    letta_agent_id = str(task.get("letta_agent_id", "")).strip()
    letta_sync_status = str(task.get("letta_sync_status", "")).strip().lower()
    letta_publish_attempted = bool(task.get("letta_publish_attempted", False))
    validator_passed = bool(task.get("validator_passed", False))
    governor_approved = bool(task.get("governor_approved", False))

    reason_codes: list[str] = []
    if not checks:
        reason_codes.extend(["validation_failed/tests_not_run", "schema_violation/validation_contract_missing_checks"])
    reason_codes.extend(checklist_reason_codes)
    if memory_required:
        for key in ("worktree_path", "candidate_changes", "evidence_refs", "commit_message", "reason_codes"):
            if key not in memory_bundle:
                reason_codes.append("schema_violation/memory_update_bundle_missing_required")
        if memory_bundle and not memory_bundle.get("commit_message"):
            reason_codes.append("validation_failed/memory_commit_missing")
        if memory_bundle and not memory_bundle.get("evidence_refs"):
            reason_codes.append("validation_failed/memory_provenance_missing")
        if bool(memory_bundle.get("defrag_run", False)) and not memory_bundle.get("relocation_pointers"):
            reason_codes.append("validation_failed/defrag_relocation_missing")
    if strict_evidence:
        reason_codes.extend(_validate_evidence_objects(evidence_objects))
    if correction_rollout:
        reason_codes.extend(_validate_correction_rollout(correction_rollout))
    if letta_runtime_enabled and not letta_agent_id:
        reason_codes.append("validation_failed/letta_agent_missing")
    if letta_runtime_enabled and not letta_sync_status:
        reason_codes.append("validation_failed/letta_sync_missing")
    if letta_runtime_enabled and letta_sync_status == "degraded":
        reason_codes.append("integration_degraded/letta_sync_failed")
    if bool(task.get("letta_sync_stale", False)):
        reason_codes.append("integration_degraded/letta_stale")
    if letta_publish_attempted and not validator_passed:
        reason_codes.append("validation_failed/letta_publish_without_gate")
    if letta_publish_attempted and not governor_approved:
        reason_codes.append("policy_violation/letta_publish_without_governor")
    if external_context_pointers:
        reason_codes.extend(_validate_letta_pointers(external_context_pointers))
    direct_external_write = bool(
        task.get("direct_external_memory_write", False)
        or task.get("external_memory_write_committed", False)
        or memory_bundle.get("direct_external_memory_write", False)
        or memory_bundle.get("external_write_committed", False)
    )
    if external_context_policy.get("direct_external_writes_forbidden", True) and direct_external_write:
        reason_codes.append("policy_violation/letta_direct_memory_write_forbidden")
    if trust_level in {"untrusted", "generated_untrusted"}:
        if not str(execution_audit.get("execution_profile", task.get("requested_profile", ""))).strip():
            reason_codes.append("validation_failed/missing_execution_profile")
        if not str(execution_audit.get("audit_ref", task.get("audit_ref", ""))).strip():
            reason_codes.append("validation_failed/missing_execution_audit_ref")
    reason_codes = sorted(set(reason_codes))

    if reason_codes:
        print(json.dumps(_fail_payload(args.run_id, reason_codes, len(checks)), indent=2))
        return 1

    contract = {
        "run_id": args.run_id,
        "checks": checks,
        "checklist_contract": checklist_contract,
        "memory_update_bundle": memory_bundle,
        "execution_audit": execution_audit,
        "evidence_objects": evidence_objects if isinstance(evidence_objects, list) else [],
        "external_context_pointers": external_context_pointers,
        "external_context_policy": external_context_policy,
        "trust_level": trust_level,
        "strict_evidence_objects": strict_evidence,
        "correction_rollout": correction_rollout,
        "max_iterations": int(task.get("max_iterations", 5)),
        "stop_conditions": task.get("stop_conditions", ["all_checks_pass"]),
        "failure_policy": "fail_closed",
        "evidence_paths": task.get("evidence_paths", []),
        "gate_scores": {
            "checks_present": {"passed": True, "weight": 0.4},
            "checklist_present": {"passed": bool(checklist_contract.get("items", [])), "weight": 0.3},
            "stop_conditions_present": {"passed": bool(task.get("stop_conditions")), "weight": 0.1},
            "evidence_paths_present": {"passed": bool(task.get("evidence_paths", [])), "weight": 0.1},
            "memory_bundle_valid": {
                "passed": (not memory_required) or (
                    bool(memory_bundle.get("worktree_path"))
                    and bool(memory_bundle.get("evidence_refs"))
                    and bool(memory_bundle.get("commit_message"))
                ),
                "weight": 0.1,
            },
            "execution_audit_valid": {
                "passed": trust_level not in {"untrusted", "generated_untrusted"}
                or (
                    bool(str(execution_audit.get("execution_profile", task.get("requested_profile", ""))).strip())
                    and bool(str(execution_audit.get("audit_ref", task.get("audit_ref", ""))).strip())
                ),
                "weight": 0.1,
            },
        },
        "progress_delta": round(min(1.0, len(checks) / 10.0), 3),
        "reason_codes": [],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / "contract.json"
    out_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "contract_path": str(out_path),
                "check_count": len(checks),
                "checklist_item_count": len(checklist_contract.get("items", [])),
                "gate_scores": contract["gate_scores"],
                "progress_delta": contract["progress_delta"],
                "reason_codes": contract["reason_codes"],
                "skill_result": {
                    "ok": True,
                    "outputs": {
                        "contract_path": str(out_path),
                        "check_count": len(checks),
                        "checklist_item_count": len(checklist_contract.get("items", [])),
                    },
                    "tool_calls": [{"tool_name": "compile_checks", "params_hash": args.run_id, "duration_ms": 0.0}],
                    "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
                    "artefact_delta": {"files_changed": [str(out_path)], "tests_run": [], "urls_fetched": []},
                    "progress_proxy": {"check_count": len(checks), "checklist_item_count": len(checklist_contract.get("items", []))},
                    "failure_codes": [],
                    "suggested_next": ["run_until_green"],
                    "gate_scores": contract["gate_scores"],
                    "progress_delta": contract["progress_delta"],
                    "reason_codes": [],
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
