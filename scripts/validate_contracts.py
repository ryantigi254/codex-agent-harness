#!/usr/bin/env python3
"""Strict contract and policy validation for codex-agent-harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "harness/skills/registry.json"
PASS_FIXTURES_DIR = ROOT / "examples/contracts/pass"
FAIL_FIXTURES_DIR = ROOT / "examples/contracts/fail"
FUZZ_FIXTURES_DIR = ROOT / "examples/contracts/fuzz"
REGRESSION_DIR = ROOT / "examples/contracts/regression"
CHECKPOINTS_DIR = ROOT / "runbooks/checks/harness_sufficiency/checkpoints"
DOCS_TO_CHECK = [
    ROOT / "README.md",
    ROOT / "docs/architecture/contracts.md",
    ROOT / "docs/architecture/safety.md",
    ROOT / "docs/architecture/evals.md",
    ROOT / "docs/architecture/memory.md",
    ROOT / "docs/architecture/overview.md",
    ROOT / "docs/architecture/routing.md",
]

SCORECARD_STABILITY_KEYS = [
    "contracts_enforced",
    "write_authority_safe",
    "routing_predictable",
    "debuggable_under_10m",
    "cost_variance_bounded",
    "learning_reversible",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bytes_len(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=True).encode("utf-8"))


def _collect_arrays(value: Any) -> list[list[Any]]:
    arrays: list[list[Any]] = []
    if isinstance(value, list):
        arrays.append(value)
        for item in value:
            arrays.extend(_collect_arrays(item))
    elif isinstance(value, dict):
        for item in value.values():
            arrays.extend(_collect_arrays(item))
    return arrays


def _collect_text_values(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value)
    elif isinstance(value, list):
        for item in value:
            texts.extend(_collect_text_values(item))
    elif isinstance(value, dict):
        for item in value.values():
            texts.extend(_collect_text_values(item))
    return texts


def _missing(payload: dict[str, Any], required: list[str], prefix: str) -> list[str]:
    return [f"schema:{prefix}:missing:{key}" for key in required if key not in payload]


def _validate_skill_result(payload: Any, limits: dict[str, int]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:skill_result:type:object_required"]
    required = ["ok", "outputs", "tool_calls", "cost_units", "artefact_delta", "failure_codes"]
    errors.extend(_missing(payload, required, "skill_result"))

    allowed = {
        "ok",
        "outputs",
        "tool_calls",
        "cost_units",
        "artefact_delta",
        "progress_proxy",
        "failure_codes",
        "suggested_next",
    }
    extra = sorted(set(payload.keys()) - allowed)
    if extra:
        errors.append("schema:skill_result:unexpected_fields_present")

    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, list):
        if len(tool_calls) > int(limits["max_tool_calls"]):
            errors.append("boundary:skill_result:tool_calls_exceeds_max")
        for idx, row in enumerate(tool_calls):
            if not isinstance(row, dict):
                errors.append(f"schema:skill_result:tool_calls[{idx}]:object_required")
                continue
            for key in ("tool_name", "params_hash", "duration_ms"):
                if key not in row:
                    errors.append(f"schema:skill_result:tool_calls[{idx}]:missing:{key}")
    elif "tool_calls" in payload:
        errors.append("schema:skill_result:type:tool_calls_array_required")

    return errors


def _validate_evidence_object(payload: Any, limits: dict[str, int]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:evidence_object:type:object_required"]

    required = ["source", "location", "span", "confidence"]
    errors.extend(_missing(payload, required, "evidence_object"))

    if "location" in payload and not isinstance(payload.get("location"), dict):
        errors.append("schema:evidence_object:location_object_required")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append("schema:evidence_object:confidence_number_required")
    else:
        c = float(confidence)
        if c < 0.0 or c > 1.0:
            errors.append("schema:evidence_object:confidence_out_of_range")

    span = payload.get("span")
    if isinstance(span, str) and _bytes_len(span) > int(limits["max_text_field_bytes"]):
        errors.append("boundary:evidence_object:span_exceeds_max_text")

    return errors


def _validate_validator_result(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:validator_result:type:object_required"]
    required = ["validator_id", "passed", "reason_codes", "evidence_refs", "gate_scores"]
    errors.extend(_missing(payload, required, "validator_result"))

    if "reason_codes" in payload and not isinstance(payload.get("reason_codes"), list):
        errors.append("schema:validator_result:reason_codes_array_required")
    if "evidence_refs" in payload and not isinstance(payload.get("evidence_refs"), list):
        errors.append("schema:validator_result:evidence_refs_array_required")
    if "gate_scores" in payload and not isinstance(payload.get("gate_scores"), dict):
        errors.append("schema:validator_result:gate_scores_object_required")

    return errors


def _validate_experience_packet(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:experience_packet:type:object_required"]

    required = [
        "run_id",
        "task_signature",
        "skill_stack_used",
        "outcome",
        "gate_status",
        "evidence_refs",
        "reason_codes",
        "cost_proxy",
    ]
    errors.extend(_missing(payload, required, "experience_packet"))

    if "skill_stack_used" in payload and not isinstance(payload.get("skill_stack_used"), list):
        errors.append("schema:experience_packet:skill_stack_used_array_required")
    if "evidence_refs" in payload and not isinstance(payload.get("evidence_refs"), list):
        errors.append("schema:experience_packet:evidence_refs_array_required")
    if "reason_codes" in payload and not isinstance(payload.get("reason_codes"), list):
        errors.append("schema:experience_packet:reason_codes_array_required")

    gate_status = payload.get("gate_status")
    if isinstance(gate_status, dict):
        if "passed" not in gate_status:
            errors.append("schema:experience_packet:gate_status_missing_passed")
    elif "gate_status" in payload:
        errors.append("schema:experience_packet:gate_status_object_required")

    return errors


def _validate_merge_policy_case(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["policy:merge_authority:payload_object_required"]
    if bool(payload.get("is_subagent_output")) and bool(payload.get("merge_to_main")):
        errors.append("policy:merge_authority:subagent_direct_merge_forbidden")
    if bool(payload.get("merge_to_main")) and not bool(payload.get("governor_review_required")):
        errors.append("policy:merge_authority:governor_review_required")
    return errors


def _validate_reward_policy_case(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["policy:reward:payload_object_required"]

    components = payload.get("reward_components", {})
    if not isinstance(components, dict):
        return ["policy:reward:reward_components_object_required"]

    if "skill_count_bonus" in components:
        errors.append("policy:reward:activity_volume_reward_forbidden")

    validator_improved = bool(payload.get("validator_improved", False))
    progress_delta = float(components.get("progress_delta", 0.0))
    if progress_delta > 0.0 and not validator_improved:
        errors.append("policy:reward:validator_improvement_required")

    return errors


def _validate_resume_checkpoint(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:opportunistic_resume_checkpoint:type:object_required"]

    required = [
        "run_id",
        "checkpoint_id",
        "context_repo_ref",
        "last_completed_work_item",
        "candidate_next_work_items",
        "selection_policy",
        "updated_at_unix",
        "governor_gate_state",
    ]
    errors.extend(_missing(payload, required, "opportunistic_resume_checkpoint"))

    candidate = payload.get("candidate_next_work_items")
    gate_state = payload.get("governor_gate_state")
    if isinstance(candidate, list):
        if gate_state == "ready" and len(candidate) == 0:
            errors.append("policy:opportunistic_resume_checkpoint:ready_requires_candidates")
    elif "candidate_next_work_items" in payload:
        errors.append("schema:opportunistic_resume_checkpoint:candidate_next_work_items_array_required")

    if "governor_gate_state" in payload and gate_state not in {"ready", "blocked", "pending_review"}:
        errors.append("schema:opportunistic_resume_checkpoint:invalid_governor_gate_state")

    return errors


def _validate_merge_audit(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:merge_authority_audit:type:object_required"]

    required = [
        "run_id",
        "proposed_diff_count",
        "rejected_by_gate_count",
        "merged_by_governor_count",
        "direct_subagent_merge_detected",
        "violations",
        "reason_codes",
    ]
    errors.extend(_missing(payload, required, "merge_authority_audit"))

    proposed = payload.get("proposed_diff_count")
    rejected = payload.get("rejected_by_gate_count")
    merged = payload.get("merged_by_governor_count")
    if isinstance(proposed, int) and isinstance(rejected, int) and isinstance(merged, int):
        if rejected + merged > proposed:
            errors.append("policy:merge_audit:invalid_count_consistency")

    if bool(payload.get("direct_subagent_merge_detected")):
        errors.append("policy:merge_audit:direct_subagent_merge_forbidden")

    return errors


def _validate_harness_task_scorecard(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:harness_task_scorecard:type:object_required"]

    required = [
        "run_id",
        "task_id",
        "task_class",
        "timestamp_unix",
        "artefact_refs",
        "stability_checks",
        "harness_plumbing_change_required",
        "failure_mode_codes",
        "notes",
    ]
    errors.extend(_missing(payload, required, "harness_task_scorecard"))

    artefact_refs = payload.get("artefact_refs")
    if isinstance(artefact_refs, dict):
        for key in ("skill_result_ref", "validator_result_ref", "experience_packet_ref"):
            if key not in artefact_refs:
                errors.append(f"schema:harness_task_scorecard:artefact_ref_missing:{key}")
    elif "artefact_refs" in payload:
        errors.append("schema:harness_task_scorecard:artefact_refs_object_required")

    checks = payload.get("stability_checks")
    if isinstance(checks, dict):
        for key in SCORECARD_STABILITY_KEYS:
            if key not in checks:
                errors.append(f"schema:harness_task_scorecard:stability_check_missing:{key}")
            elif not isinstance(checks.get(key), bool):
                errors.append(f"schema:harness_task_scorecard:stability_check_bool_required:{key}")
    elif "stability_checks" in payload:
        errors.append("schema:harness_task_scorecard:stability_checks_object_required")

    return errors


def _validate_harness_sufficiency_checkpoint(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["schema:harness_sufficiency_checkpoint:type:object_required"]

    required = ["checkpoint_id", "window_start", "window_end", "task_pack_ref", "runs", "summary", "go_no_go"]
    errors.extend(_missing(payload, required, "harness_sufficiency_checkpoint"))

    runs = payload.get("runs")
    if isinstance(runs, list):
        if len(runs) != 20:
            errors.append("policy:harness_checkpoint:runs_must_be_20")
    elif "runs" in payload:
        errors.append("schema:harness_sufficiency_checkpoint:runs_array_required")

    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in (
            "total_runs",
            "harness_plumbing_change_runs",
            "harness_plumbing_change_rate",
            "stability_criteria_pass_map",
            "evidence_coverage_ratio",
            "routing_consistency_ratio",
            "cost_variance_by_class",
        ):
            if key not in summary:
                errors.append(f"schema:harness_sufficiency_checkpoint:summary_missing:{key}")

        total_runs = summary.get("total_runs")
        plumbing_runs = summary.get("harness_plumbing_change_runs")
        rate = summary.get("harness_plumbing_change_rate")
        if isinstance(total_runs, int) and isinstance(plumbing_runs, int) and isinstance(rate, (int, float)) and total_runs > 0:
            expected = plumbing_runs / total_runs
            if abs(float(rate) - expected) > 1e-9:
                errors.append("policy:harness_checkpoint:invalid_plumbing_rate_math")

        sc_map = summary.get("stability_criteria_pass_map")
        if isinstance(sc_map, dict):
            for key in SCORECARD_STABILITY_KEYS:
                if key not in sc_map:
                    errors.append(f"schema:harness_sufficiency_checkpoint:stability_map_missing:{key}")
        elif "stability_criteria_pass_map" in summary:
            errors.append("schema:harness_sufficiency_checkpoint:stability_map_object_required")
    elif "summary" in payload:
        errors.append("schema:harness_sufficiency_checkpoint:summary_object_required")

    go_no_go = payload.get("go_no_go")
    if isinstance(go_no_go, dict):
        status = go_no_go.get("status")
        failed = go_no_go.get("failed_conditions")
        if status not in {"go", "no_go"}:
            errors.append("schema:harness_sufficiency_checkpoint:invalid_status")
        if isinstance(failed, list):
            if failed and status != "no_go":
                errors.append("policy:harness_checkpoint:status_must_be_no_go_when_failed_conditions_present")
            if not failed and status == "no_go":
                errors.append("policy:harness_checkpoint:no_go_requires_failed_conditions")
        else:
            errors.append("schema:harness_sufficiency_checkpoint:failed_conditions_array_required")
    elif "go_no_go" in payload:
        errors.append("schema:harness_sufficiency_checkpoint:go_no_go_object_required")

    return errors


def _validate_boundaries(payload: Any, limits: dict[str, int], label: str) -> list[str]:
    errors: list[str] = []
    if _bytes_len(payload) > int(limits["max_payload_bytes"]):
        errors.append(f"boundary:{label}:payload_exceeds_max")
    for arr in _collect_arrays(payload):
        if len(arr) > int(limits["max_array_items"]):
            errors.append(f"boundary:{label}:array_exceeds_max")
            break
    for text in _collect_text_values(payload):
        if _bytes_len(text) > int(limits["max_text_field_bytes"]):
            errors.append(f"boundary:{label}:text_exceeds_max")
            break
    return errors


def validate_contract(contract: str, payload: Any, limits: dict[str, int]) -> list[str]:
    if contract == "skill_result":
        return _validate_skill_result(payload, limits) + _validate_boundaries(payload, limits, "skill_result")
    if contract == "evidence_object":
        return _validate_evidence_object(payload, limits) + _validate_boundaries(payload, limits, "evidence_object")
    if contract == "validator_result":
        return _validate_validator_result(payload) + _validate_boundaries(payload, limits, "validator_result")
    if contract == "experience_packet":
        return _validate_experience_packet(payload) + _validate_boundaries(payload, limits, "experience_packet")
    if contract == "merge_authority_policy":
        return _validate_merge_policy_case(payload)
    if contract == "reward_policy":
        return _validate_reward_policy_case(payload)
    if contract == "opportunistic_resume_checkpoint":
        return _validate_resume_checkpoint(payload)
    if contract == "merge_authority_audit":
        return _validate_merge_audit(payload)
    if contract == "harness_task_scorecard":
        return _validate_harness_task_scorecard(payload)
    if contract == "harness_sufficiency_checkpoint":
        return _validate_harness_sufficiency_checkpoint(payload)
    return [f"fixture:unknown_contract:{contract}"]


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(registry.get("contracts_version", "")) != "2.0":
        errors.append("registry:contracts_version_must_be_2_0")

    for key in (
        "skills_version",
        "contracts_version",
        "contract_catalog",
        "skills",
        "boundaries_policy_id",
        "merge_authority_policy_id",
        "reward_policy_id",
        "governance_contract_ids",
        "policies",
    ):
        if key not in registry:
            errors.append(f"registry:missing:{key}")

    catalog = registry.get("contract_catalog", {})
    if not isinstance(catalog, dict):
        errors.append("registry:contract_catalog_object_required")
        return errors

    required_catalog_keys = {
        "skill_result",
        "evidence_object",
        "validator_result",
        "experience_packet",
        "output_boundaries",
        "merge_authority_policy",
        "reward_policy",
        "merge_authority_audit",
        "opportunistic_resume_checkpoint",
        "harness_task_scorecard",
        "harness_sufficiency_checkpoint",
    }
    for key in required_catalog_keys:
        if key not in catalog:
            errors.append(f"registry:contract_catalog_missing:{key}")
        else:
            schema_path = ROOT / str(catalog[key])
            if not schema_path.exists():
                errors.append(f"registry:contract_catalog_path_missing:{key}")

    governance_ids = registry.get("governance_contract_ids", {})
    if not isinstance(governance_ids, dict):
        errors.append("registry:governance_contract_ids_object_required")
    else:
        for key in required_catalog_keys - {"skill_result", "evidence_object", "validator_result", "experience_packet"}:
            if key not in governance_ids:
                errors.append(f"registry:governance_contract_ids_missing:{key}")
            elif governance_ids.get(key) != key:
                errors.append(f"registry:governance_contract_ids_mismatch:{key}")

    skills = registry.get("skills", [])
    if not isinstance(skills, list) or not skills:
        errors.append("registry:skills_array_required")
        return errors

    for idx, skill in enumerate(skills):
        if not isinstance(skill, dict):
            errors.append(f"registry:skills[{idx}]:object_required")
            continue
        for key in ("name", "type", "inputs_schema", "outputs_schema", "depends_on", "triggers", "contract_ids"):
            if key not in skill:
                errors.append(f"registry:skills[{idx}]:missing:{key}")

        contract_ids = skill.get("contract_ids")
        if not isinstance(contract_ids, dict):
            errors.append(f"registry:skills[{idx}]:contract_ids_object_required")
            continue
        for key in ("skill_result", "evidence_object", "validator_result", "experience_packet"):
            if key not in contract_ids:
                errors.append(f"registry:skills[{idx}]:contract_ids_missing:{key}")
            elif contract_ids.get(key) != key:
                errors.append(f"registry:skills[{idx}]:contract_ids_mismatch:{key}")

    return errors


def validate_schema_files(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, rel in catalog.items():
        schema_path = ROOT / str(rel)
        if not schema_path.exists():
            errors.append(f"schema_file:missing:{key}")
            continue
        try:
            payload = load_json(schema_path)
        except Exception:
            errors.append(f"schema_file:invalid_json:{key}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"schema_file:not_object:{key}")
            continue
        for required_key in ("$schema", "$id", "title", "type"):
            if required_key not in payload:
                errors.append(f"schema_file:missing_{required_key}:{key}")
    return errors


def _validate_fixture_file(path: Path, limits: dict[str, int], pass_mode: bool) -> list[str]:
    errors: list[str] = []
    fixture = load_json(path)
    contract = str(fixture.get("contract", ""))
    payload = fixture.get("payload")
    result = validate_contract(contract, payload, limits)

    if pass_mode:
        if result:
            errors.append(f"fixture:pass:{path.name}:unexpected_errors:{','.join(result)}")
        return errors

    expected_errors = fixture.get("expected_errors", [])
    if not isinstance(expected_errors, list) or not expected_errors:
        errors.append(f"fixture:fail:{path.name}:missing_expected_errors")
        return errors
    for expected in expected_errors:
        if expected not in result:
            errors.append(f"fixture:fail:{path.name}:expected_not_found:{expected}")
    return errors


def validate_fixtures(limits: dict[str, int]) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    counts = {"contracts_checked": 0}

    for path in sorted(PASS_FIXTURES_DIR.glob("*.json")):
        errors.extend(_validate_fixture_file(path, limits, True))
        counts["contracts_checked"] += 1

    for path in sorted(FAIL_FIXTURES_DIR.glob("*.json")):
        errors.extend(_validate_fixture_file(path, limits, False))
        counts["contracts_checked"] += 1

    return errors, counts


def validate_fuzz(limits: dict[str, int]) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    stats = {"fuzz_cases_passed": 0, "fuzz_cases_failed": 0}

    for path in sorted(FUZZ_FIXTURES_DIR.glob("*.json")):
        fixture = load_json(path)
        expected_errors = fixture.get("expected_errors", [])
        if not isinstance(expected_errors, list) or not expected_errors:
            errors.append(f"fuzz:{path.name}:missing_expected_errors")
            stats["fuzz_cases_failed"] += 1
            continue

        contract = str(fixture.get("contract", ""))
        payload = fixture.get("payload")
        result = validate_contract(contract, payload, limits)
        missing = [err for err in expected_errors if err not in result]
        if missing:
            errors.append(f"fuzz:{path.name}:expected_not_found:{','.join(missing)}")
            stats["fuzz_cases_failed"] += 1
        else:
            stats["fuzz_cases_passed"] += 1

    return errors, stats


def validate_policies(registry: dict[str, Any]) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    stats = {"policy_violations": 0}

    policies = registry.get("policies", {})
    if not isinstance(policies, dict):
        return ["policy:registry_policies_object_required"], {"policy_violations": 1}

    boundaries = policies.get("output_boundaries", {})
    merge_policy = policies.get("merge_authority", {})
    reward_policy = policies.get("reward_policy", {})

    if not isinstance(boundaries, dict):
        errors.append("policy:output_boundaries_object_required")
    else:
        for key, expected in {
            "max_payload_bytes": 262144,
            "max_array_items": 200,
            "max_text_field_bytes": 65536,
            "max_tool_calls": 200,
        }.items():
            if int(boundaries.get(key, -1)) != expected:
                errors.append(f"policy:output_boundaries_unexpected:{key}")

    if not isinstance(merge_policy, dict):
        errors.append("policy:merge_authority_object_required")
    else:
        if not bool(merge_policy.get("subagent_proposal_only")):
            errors.append("policy:merge_authority:subagent_proposal_only_required")
        if not bool(merge_policy.get("governor_review_required")):
            errors.append("policy:merge_authority:governor_review_required")
        if not bool(merge_policy.get("validator_gate_required")):
            errors.append("policy:merge_authority:validator_gate_required")

    if not isinstance(reward_policy, dict):
        errors.append("policy:reward_policy_object_required")
    else:
        if not bool(reward_policy.get("disallow_activity_volume_reward")):
            errors.append("policy:reward:activity_volume_reward_forbidden")
        if not bool(reward_policy.get("positive_progress_requires_validator_improved")):
            errors.append("policy:reward:validator_improvement_required")

    stats["policy_violations"] = len(errors)
    return errors, stats


def validate_regression_pack(limits: dict[str, int]) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    stats = {"reason_code_drift_failures": 0}

    for pack in sorted(REGRESSION_DIR.glob("*.json")):
        payload = load_json(pack)
        cases = payload.get("cases", [])
        if not isinstance(cases, list):
            errors.append(f"regression:{pack.name}:cases_array_required")
            continue

        for idx, case in enumerate(cases):
            if not isinstance(case, dict):
                errors.append(f"regression:{pack.name}:case_{idx}:object_required")
                stats["reason_code_drift_failures"] += 1
                continue

            fixture_path = case.get("fixture")
            must_pass = bool(case.get("must_pass"))
            expected_errors = case.get("expected_errors", [])
            if not isinstance(fixture_path, str):
                errors.append(f"regression:{pack.name}:case_{idx}:fixture_required")
                stats["reason_code_drift_failures"] += 1
                continue

            file_path = ROOT / "examples/contracts" / fixture_path
            if not file_path.exists():
                errors.append(f"regression:{pack.name}:case_{idx}:fixture_missing")
                stats["reason_code_drift_failures"] += 1
                continue

            fixture = load_json(file_path)
            actual = validate_contract(str(fixture.get("contract", "")), fixture.get("payload"), limits)

            if must_pass and actual:
                errors.append(f"regression:{pack.name}:case_{idx}:expected_pass_got_errors")
                stats["reason_code_drift_failures"] += 1
            if not must_pass:
                if not isinstance(expected_errors, list) or not expected_errors:
                    errors.append(f"regression:{pack.name}:case_{idx}:expected_errors_required")
                    stats["reason_code_drift_failures"] += 1
                else:
                    missing = [err for err in expected_errors if err not in actual]
                    if missing:
                        errors.append(f"regression:{pack.name}:case_{idx}:missing_reason_codes:{','.join(missing)}")
                        stats["reason_code_drift_failures"] += 1

    return errors, stats


def checkpoint_readiness_counts() -> dict[str, int]:
    stats = {
        "checkpoint_runs_count": 0,
        "checkpoint_go_count": 0,
        "checkpoint_no_go_count": 0,
        "missing_stability_proof_count": 0,
    }
    if not CHECKPOINTS_DIR.exists():
        return stats

    for path in sorted(CHECKPOINTS_DIR.glob("*.json")):
        try:
            payload = load_json(path)
        except Exception:
            stats["missing_stability_proof_count"] += 1
            continue

        if not isinstance(payload, dict):
            stats["missing_stability_proof_count"] += 1
            continue

        stats["checkpoint_runs_count"] += 1
        go_no_go = payload.get("go_no_go", {})
        status = go_no_go.get("status") if isinstance(go_no_go, dict) else None
        if status == "go":
            stats["checkpoint_go_count"] += 1
        elif status == "no_go":
            stats["checkpoint_no_go_count"] += 1

        summary = payload.get("summary", {})
        sc_map = summary.get("stability_criteria_pass_map", {}) if isinstance(summary, dict) else {}
        if not isinstance(sc_map, dict):
            stats["missing_stability_proof_count"] += 1
            continue
        if any(k not in sc_map for k in SCORECARD_STABILITY_KEYS):
            stats["missing_stability_proof_count"] += 1

    return stats


def validate_docs_consistency() -> list[str]:
    errors: list[str] = []
    required_tokens = [
        "SkillResult",
        "EvidenceObject",
        "ValidatorResult",
        "ExperiencePacket",
        "harness_task_scorecard",
        "harness_sufficiency_checkpoint",
        "20-task",
        "go/no-go",
        "max_payload_bytes",
        "subagents propose diffs",
        "only governor can merge",
        "validator-improving progress",
        "diagram.control-plane.mmd",
        "diagram.evidence-gates.mmd",
        "diagram.learning-memory.mmd",
        "merge_authority_audit",
        "opportunistic_resume_checkpoint",
        "CI",
    ]

    combined = ""
    for path in DOCS_TO_CHECK:
        if not path.exists():
            errors.append(f"docs:missing:{path.name}")
            continue
        combined += path.read_text(encoding="utf-8") + "\n"

    for token in required_tokens:
        if token not in combined:
            errors.append(f"docs:missing_token:{token}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Run full strict validation.")
    parser.add_argument("--lint-only", action="store_true", help="Run registry and schema lint only.")
    parser.add_argument("--policy-only", action="store_true", help="Run policy checks only.")
    parser.add_argument("--docs-only", action="store_true", help="Run docs consistency checks only.")
    parser.add_argument("--regression-pack", action="store_true", help="Run regression pack checks only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = load_json(REGISTRY_PATH)
    if not isinstance(registry, dict):
        print("[FAIL] registry must be a JSON object")
        return 2

    catalog = registry.get("contract_catalog", {}) if isinstance(registry.get("contract_catalog", {}), dict) else {}
    limits = registry.get("policies", {}).get("output_boundaries", {})
    if not isinstance(limits, dict):
        limits = {}

    boundary_limits = {
        "max_payload_bytes": int(limits.get("max_payload_bytes", 262144)),
        "max_array_items": int(limits.get("max_array_items", 200)),
        "max_text_field_bytes": int(limits.get("max_text_field_bytes", 65536)),
        "max_tool_calls": int(limits.get("max_tool_calls", 200)),
    }

    errors: list[str] = []
    summary = {
        "contracts_checked": 0,
        "registry_coverage_failures": 0,
        "fuzz_cases_passed": 0,
        "fuzz_cases_failed": 0,
        "merge_audit_violations": 0,
        "checkpoint_contract_violations": 0,
        "reason_code_drift_failures": 0,
        "boundary_violations": 0,
        "policy_violations": 0,
        "checkpoint_runs_count": 0,
        "checkpoint_go_count": 0,
        "checkpoint_no_go_count": 0,
        "missing_stability_proof_count": 0,
    }

    def ingest(new_errors: list[str]) -> None:
        errors.extend(new_errors)

    if args.docs_only:
        ingest(validate_docs_consistency())
    elif args.lint_only:
        registry_errors = validate_registry(registry)
        schema_errors = validate_schema_files(catalog)
        summary["registry_coverage_failures"] = len(
            [e for e in registry_errors if e.startswith("registry:skills[") and "contract_ids" in e]
        )
        ingest(registry_errors)
        ingest(schema_errors)
    elif args.policy_only:
        policy_errors, policy_stats = validate_policies(registry)
        fixture_errors, fixture_counts = validate_fixtures(boundary_limits)
        ingest(policy_errors)
        ingest(fixture_errors)
        summary["policy_violations"] = policy_stats["policy_violations"]
        summary["contracts_checked"] = fixture_counts["contracts_checked"]
    elif args.regression_pack:
        regression_errors, regression_stats = validate_regression_pack(boundary_limits)
        ingest(regression_errors)
        summary["reason_code_drift_failures"] = regression_stats["reason_code_drift_failures"]
    else:
        registry_errors = validate_registry(registry)
        schema_errors = validate_schema_files(catalog)
        policy_errors, policy_stats = validate_policies(registry)
        fixture_errors, fixture_counts = validate_fixtures(boundary_limits)
        fuzz_errors, fuzz_stats = validate_fuzz(boundary_limits)
        regression_errors, regression_stats = validate_regression_pack(boundary_limits)
        docs_errors = validate_docs_consistency()

        ingest(registry_errors)
        ingest(schema_errors)
        ingest(policy_errors)
        ingest(fixture_errors)
        ingest(fuzz_errors)
        ingest(regression_errors)
        ingest(docs_errors)

        summary["contracts_checked"] = fixture_counts["contracts_checked"]
        summary["registry_coverage_failures"] = len(
            [e for e in registry_errors if e.startswith("registry:skills[") and "contract_ids" in e]
        )
        summary["fuzz_cases_passed"] = fuzz_stats["fuzz_cases_passed"]
        summary["fuzz_cases_failed"] = fuzz_stats["fuzz_cases_failed"]
        summary["reason_code_drift_failures"] = regression_stats["reason_code_drift_failures"]
        summary["policy_violations"] = policy_stats["policy_violations"]

    summary["merge_audit_violations"] = len([e for e in errors if e.startswith("policy:merge_audit:")])
    summary["checkpoint_contract_violations"] = len([e for e in errors if "harness_sufficiency_checkpoint" in e or "harness_task_scorecard" in e])
    summary["boundary_violations"] = len([e for e in errors if e.startswith("boundary:")])

    readiness = checkpoint_readiness_counts()
    summary.update(readiness)

    if errors:
        print("[FAIL] validation errors:")
        for err in errors:
            print(f"- {err}")
        print("[SUMMARY]")
        for key, value in summary.items():
            print(f"- {key}: {value}")
        return 2

    print("[PASS] strict contract validation succeeded.")
    print("[SUMMARY]")
    for key, value in summary.items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
