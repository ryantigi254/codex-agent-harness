#!/usr/bin/env python3
"""Strict contract and policy validation for codex-agent-harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "harness/skills/registry.json"
SCHEMA_DIR = ROOT / "harness/skills/schemas"
PASS_FIXTURES_DIR = ROOT / "examples/contracts/pass"
FAIL_FIXTURES_DIR = ROOT / "examples/contracts/fail"
DOCS_TO_CHECK = [
    ROOT / "README.md",
    ROOT / "docs/architecture/contracts.md",
    ROOT / "docs/architecture/safety.md",
    ROOT / "docs/architecture/evals.md",
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
    else:
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
        if float(confidence) < 0.0 or float(confidence) > 1.0:
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
    required = ["run_id", "task_signature", "skill_stack_used", "outcome", "gate_status", "evidence_refs", "reason_codes", "cost_proxy"]
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


def _validate_boundaries(payload: Any, limits: dict[str, int], label: str) -> list[str]:
    errors: list[str] = []
    if _bytes_len(payload) > int(limits["max_payload_bytes"]):
        errors.append(f"boundary:{label}:payload_exceeds_max")
    for array_value in _collect_arrays(payload):
        if len(array_value) > int(limits["max_array_items"]):
            errors.append(f"boundary:{label}:array_exceeds_max")
            break
    for text_value in _collect_text_values(payload):
        if _bytes_len(text_value) > int(limits["max_text_field_bytes"]):
            errors.append(f"boundary:{label}:text_exceeds_max")
            break
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


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(registry.get("contracts_version", "")) != "2.0":
        errors.append("registry:contracts_version_must_be_2_0")
    for key in ("skills_version", "contracts_version", "contract_catalog", "skills", "boundaries_policy_id", "merge_authority_policy_id", "reward_policy_id", "policies"):
        if key not in registry:
            errors.append(f"registry:missing:{key}")
    skills = registry.get("skills", [])
    if not isinstance(skills, list) or not skills:
        errors.append("registry:skills_array_required")
        return errors
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
    }
    for key in required_catalog_keys:
        if key not in catalog:
            errors.append(f"registry:contract_catalog_missing:{key}")
        else:
            schema_path = ROOT / str(catalog[key])
            if not schema_path.exists():
                errors.append(f"registry:contract_catalog_path_missing:{key}")

    for idx, skill in enumerate(skills):
        if not isinstance(skill, dict):
            errors.append(f"registry:skills[{idx}]:object_required")
            continue
        for key in ("name", "type", "inputs_schema", "outputs_schema", "depends_on", "triggers", "contract_ids"):
            if key not in skill:
                errors.append(f"registry:skills[{idx}]:missing:{key}")
        contract_ids = skill.get("contract_ids", {})
        if isinstance(contract_ids, dict):
            for key in ("skill_result", "evidence_object", "validator_result", "experience_packet"):
                if key not in contract_ids:
                    errors.append(f"registry:skills[{idx}]:contract_ids_missing:{key}")
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


def validate_fixtures(limits: dict[str, int]) -> list[str]:
    errors: list[str] = []

    def validate_contract(contract: str, payload: Any) -> list[str]:
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
        return [f"fixture:unknown_contract:{contract}"]

    for path in sorted(PASS_FIXTURES_DIR.glob("*.json")):
        fixture = load_json(path)
        contract = str(fixture.get("contract", ""))
        payload = fixture.get("payload")
        fixture_errors = validate_contract(contract, payload)
        if fixture_errors:
            errors.append(f"fixture:pass:{path.name}:unexpected_errors:{','.join(fixture_errors)}")

    for path in sorted(FAIL_FIXTURES_DIR.glob("*.json")):
        fixture = load_json(path)
        contract = str(fixture.get("contract", ""))
        payload = fixture.get("payload")
        expected_errors = fixture.get("expected_errors", [])
        if not isinstance(expected_errors, list) or not expected_errors:
            errors.append(f"fixture:fail:{path.name}:missing_expected_errors")
            continue
        fixture_errors = validate_contract(contract, payload)
        for expected in expected_errors:
            if expected not in fixture_errors:
                errors.append(f"fixture:fail:{path.name}:expected_not_found:{expected}")
    return errors


def validate_policies(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policies = registry.get("policies", {})
    if not isinstance(policies, dict):
        return ["policy:registry_policies_object_required"]
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
    return errors


def validate_docs_consistency() -> list[str]:
    errors: list[str] = []
    required_tokens = [
        "SkillResult",
        "EvidenceObject",
        "ValidatorResult",
        "ExperiencePacket",
        "max_payload_bytes",
        "subagents propose diffs",
        "only governor can merge",
        "validator-improving progress",
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
    if args.docs_only:
        errors.extend(validate_docs_consistency())
    elif args.policy_only:
        errors.extend(validate_policies(registry))
        errors.extend(validate_fixtures(boundary_limits))
    elif args.lint_only:
        errors.extend(validate_registry(registry))
        errors.extend(validate_schema_files(catalog))
    else:
        errors.extend(validate_registry(registry))
        errors.extend(validate_schema_files(catalog))
        errors.extend(validate_policies(registry))
        errors.extend(validate_fixtures(boundary_limits))
        errors.extend(validate_docs_consistency())
        if args.strict:
            pass

    if errors:
        print("[FAIL] validation errors:")
        for err in errors:
            print(f"- {err}")
        return 2

    print("[PASS] strict contract validation succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
