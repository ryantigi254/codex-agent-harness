#!/usr/bin/env python3
"""Run tool contract enforcement checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TYPE_MAP = {"string": str, "number": (int, float), "boolean": bool, "array": list, "object": dict}
SKILL_RESULT_REQUIRED = [
    "ok",
    "outputs",
    "tool_calls",
    "cost_units",
    "artefact_delta",
    "progress_proxy",
    "failure_codes",
    "suggested_next",
]
CHECKLIST_REQUIRED = ["run_id", "items", "termination_policy", "reason_codes", "version"]
CHECKLIST_ITEM_REQUIRED = [
    "item_id",
    "question",
    "evidence_required",
    "strictness",
    "depends_on",
    "status",
    "satisfied_at_step",
    "evidence_refs",
]
LIMITS_PATH = Path("/Users/ryangichuru/.codex/skills/scripts/output_boundary_limits.json")
EVIDENCE_SCHEMA_PATH = Path("/Users/ryangichuru/.codex/skills/scripts/evidence_object_schema.json")
LETTA_POINTER_SCHEMA_PATH = Path("/Users/ryangichuru/.codex/skills/scripts/letta_pointer_contract_schema.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _detect_cycle(items: list[dict[str, Any]]) -> bool:
    graph: dict[str, list[str]] = {
        str(item.get("item_id", "")): [str(dep) for dep in item.get("depends_on", []) if isinstance(dep, str)]
        for item in items
        if isinstance(item, dict)
    }
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


def _load_limits() -> dict[str, int]:
    if not LIMITS_PATH.exists():
        return {
            "max_payload_bytes": 262144,
            "max_array_items": 200,
            "max_text_field_bytes": 65536,
            "max_tool_calls": 200,
        }
    payload = read_json(LIMITS_PATH)
    if not isinstance(payload, dict):
        return {
            "max_payload_bytes": 262144,
            "max_array_items": 200,
            "max_text_field_bytes": 65536,
            "max_tool_calls": 200,
        }
    return {
        "max_payload_bytes": int(payload.get("max_payload_bytes", 262144)),
        "max_array_items": int(payload.get("max_array_items", 200)),
        "max_text_field_bytes": int(payload.get("max_text_field_bytes", 65536)),
        "max_tool_calls": int(payload.get("max_tool_calls", 200)),
    }


def _collect_text_fields(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value)
        return texts
    if isinstance(value, list):
        for item in value:
            texts.extend(_collect_text_fields(item))
        return texts
    if isinstance(value, dict):
        for item in value.values():
            texts.extend(_collect_text_fields(item))
    return texts


def _collect_arrays(value: Any) -> list[list[Any]]:
    arrays: list[list[Any]] = []
    if isinstance(value, list):
        arrays.append(value)
        for item in value:
            arrays.extend(_collect_arrays(item))
        return arrays
    if isinstance(value, dict):
        for item in value.values():
            arrays.extend(_collect_arrays(item))
    return arrays


def _extract_evidence_objects(payload: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    for key in ("evidence_objects", "evidence_refs", "minimal_repro_refs", "source_pointers"):
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
    checklist_payload = payload.get("checklist_payload")
    if isinstance(checklist_payload, dict):
        items = checklist_payload.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    evidence_refs = item.get("evidence_refs", [])
                    if isinstance(evidence_refs, list):
                        values.extend(evidence_refs)
    return values


def _extract_external_context_pointers(payload: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    for key in ("external_context_pointers", "external_context_refs"):
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
    memory_frontmatter = payload.get("memory_frontmatter")
    if isinstance(memory_frontmatter, dict):
        raw = memory_frontmatter.get("external_context_pointers", [])
        if isinstance(raw, list):
            values.extend(raw)
    return values


def _validate_evidence_object(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["schema_violation/evidence_object_invalid_type"]
    for key in ("source", "location", "span", "confidence"):
        if key not in value:
            errors.append("schema_violation/evidence_object_missing_required")
    if "location" in value and not isinstance(value.get("location"), dict):
        errors.append("schema_violation/evidence_object_invalid_type")
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append("schema_violation/evidence_object_invalid_type")
    else:
        if float(confidence) < 0.0 or float(confidence) > 1.0:
            errors.append("validation_failed/evidence_confidence_out_of_range")
    span = value.get("span")
    if span is not None and not isinstance(span, (str, dict)):
        errors.append("schema_violation/evidence_object_invalid_type")
    source = value.get("source")
    if source is not None and not isinstance(source, str):
        errors.append("schema_violation/evidence_object_invalid_type")
    return errors


def _validate_letta_pointer(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["schema_violation/letta_pointer_invalid_type"]
    required = (
        "provider",
        "folder_id",
        "document_id",
        "source_uri",
        "content_hash",
        "synced_at_unix",
        "provenance_tag",
    )
    for key in required:
        if key not in value:
            errors.append("schema_violation/letta_pointer_missing_required")
    if value.get("provider") not in (None, "letta"):
        errors.append("schema_violation/letta_pointer_invalid_type")
    if not str(value.get("content_hash", "")).strip():
        errors.append("validation_failed/letta_pointer_hash_missing")
    synced_at = value.get("synced_at_unix")
    if synced_at is not None and not isinstance(synced_at, (int, float)):
        errors.append("schema_violation/letta_pointer_invalid_type")
    elif isinstance(synced_at, (int, float)) and float(synced_at) <= 0:
        errors.append("validation_failed/letta_pointer_stale_sync")
    if value.get("stale", False) is True or value.get("is_stale", False) is True:
        errors.append("validation_failed/letta_pointer_stale_sync")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--strict-skill-result", action="store_true")
    parser.add_argument("--strict-checklist", action="store_true")
    parser.add_argument("--strict-output-boundaries", action="store_true")
    args = parser.parse_args()

    root = read_json(args.input) if args.input.exists() else {}
    if not isinstance(root, dict):
        print(json.dumps({"ok": False, "error": "input must be object"}, ensure_ascii=True))
        return 2
    payload = root.get("payload", {})
    required_fields = root.get("required_fields", [])
    required_types = root.get("required_types", {})
    validate_skill_result = bool(root.get("validate_skill_result", False))
    validate_checklist_contract = bool(root.get("validate_checklist_contract", False))
    validate_evidence_objects = bool(root.get("validate_evidence_objects", False))
    checklist_payload = root.get("checklist_payload")
    limits = _load_limits()

    if not isinstance(payload, dict):
        payload = {}

    missing = [field for field in required_fields if field not in payload]
    type_errors = []
    for field, expected in required_types.items():
        if field not in payload:
            continue
        py_type = TYPE_MAP.get(expected)
        if py_type and not isinstance(payload[field], py_type):
            type_errors.append(field)

    warnings: list[str] = []
    failure_codes: list[str] = []

    skill_result = payload.get("skill_result", payload)
    if validate_skill_result:
        if not isinstance(skill_result, dict):
            failure_codes.append("skill_result_not_object")
            missing.extend(SKILL_RESULT_REQUIRED)
        else:
            sr_missing = [key for key in SKILL_RESULT_REQUIRED if key not in skill_result]
            missing.extend(sr_missing)
            if sr_missing:
                failure_codes.append("skill_result_missing_required")
            sr_type_errors = []
            type_expectations = {
                "ok": bool,
                "outputs": dict,
                "tool_calls": list,
                "cost_units": dict,
                "artefact_delta": dict,
                "failure_codes": list,
            }
            for key, expected in type_expectations.items():
                if key in skill_result and not isinstance(skill_result[key], expected):
                    sr_type_errors.append(key)
            if sr_type_errors:
                type_errors.extend([f"skill_result.{key}" for key in sr_type_errors])
                failure_codes.append("skill_result_type_error")
            tool_calls = skill_result.get("tool_calls", [])
            if isinstance(tool_calls, list) and len(tool_calls) > int(limits["max_tool_calls"]):
                failure_codes.append("schema_violation/output_array_too_large")
        if not args.strict_skill_result and (missing or type_errors):
            warnings.append("compat_mode_skill_result_violation")
            missing = []
            type_errors = []

    checklist_value = checklist_payload if checklist_payload is not None else payload.get("checklist_payload")
    if validate_checklist_contract:
        if not isinstance(checklist_value, dict):
            failure_codes.append("checklist_contract_missing_required")
            missing.extend([f"checklist.{key}" for key in CHECKLIST_REQUIRED])
        else:
            cl_missing = [key for key in CHECKLIST_REQUIRED if key not in checklist_value]
            if cl_missing:
                missing.extend([f"checklist.{key}" for key in cl_missing])
                failure_codes.append("checklist_contract_missing_required")

            items = checklist_value.get("items", []) if isinstance(checklist_value.get("items", []), list) else []
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    type_errors.append(f"checklist.items[{idx}]")
                    failure_codes.append("checklist_contract_missing_required")
                    continue
                item_missing = [key for key in CHECKLIST_ITEM_REQUIRED if key not in item]
                if item_missing:
                    missing.extend([f"checklist.items[{idx}].{key}" for key in item_missing])
                    failure_codes.append("checklist_contract_missing_required")
                strictness = item.get("strictness")
                if strictness not in {"strict", "normal"}:
                    failure_codes.append("checklist_invalid_strictness")
            if _detect_cycle(items):
                failure_codes.append("checklist_dependency_cycle")
            for item in items:
                if not isinstance(item, dict):
                    continue
                ev = item.get("evidence_required", [])
                if isinstance(ev, list) and any(not str(v).strip() for v in ev):
                    failure_codes.append("checklist_evidence_missing")

        if not args.strict_checklist and any(code.startswith("checklist_") for code in failure_codes):
            warnings.append("compat_mode_checklist_violation")
            missing = [field for field in missing if not field.startswith("checklist.")]
            type_errors = [field for field in type_errors if not field.startswith("checklist.")]
            failure_codes = [code for code in failure_codes if not code.startswith("checklist_")]

    evidence_values = _extract_evidence_objects(payload)
    if validate_evidence_objects and evidence_values:
        for value in evidence_values:
            failure_codes.extend(_validate_evidence_object(value))
    external_pointer_values = _extract_external_context_pointers(payload)
    if external_pointer_values:
        for value in external_pointer_values:
            failure_codes.extend(_validate_letta_pointer(value))
    letta_runtime_enabled = bool(payload.get("letta_runtime_enabled", False))
    letta_agent_id = str(payload.get("letta_agent_id", "")).strip()
    letta_sync_status = str(payload.get("letta_sync_status", "")).strip().lower()
    letta_publish_attempted = bool(payload.get("letta_publish_attempted", False))
    validator_passed = bool(payload.get("validator_passed", False))
    governor_approved = bool(payload.get("governor_approved", False))
    if letta_runtime_enabled and not letta_agent_id:
        failure_codes.append("validation_failed/letta_agent_missing")
    if letta_runtime_enabled and not letta_sync_status:
        failure_codes.append("validation_failed/letta_sync_missing")
    if letta_runtime_enabled and letta_sync_status == "degraded":
        failure_codes.append("integration_degraded/letta_sync_failed")
    if bool(payload.get("letta_sync_stale", False)):
        failure_codes.append("integration_degraded/letta_stale")
    if letta_publish_attempted and not validator_passed:
        failure_codes.append("validation_failed/letta_publish_without_gate")
    if letta_publish_attempted and not governor_approved:
        failure_codes.append("policy_violation/letta_publish_without_governor")
    if bool(payload.get("direct_external_memory_write", False)) or bool(payload.get("external_memory_write_committed", False)):
        failure_codes.append("policy_violation/letta_direct_memory_write_forbidden")

    payload_bytes = len(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
    if payload_bytes > int(limits["max_payload_bytes"]):
        failure_codes.append("schema_violation/output_payload_too_large")

    for array_value in _collect_arrays(payload):
        if len(array_value) > int(limits["max_array_items"]):
            failure_codes.append("schema_violation/output_array_too_large")
            break

    for text_value in _collect_text_fields(payload):
        if len(text_value.encode("utf-8")) > int(limits["max_text_field_bytes"]):
            failure_codes.append("schema_violation/output_text_field_too_large")
            break

    if not args.strict_output_boundaries:
        boundary_codes = {
            "schema_violation/output_payload_too_large",
            "schema_violation/output_array_too_large",
            "schema_violation/output_text_field_too_large",
            "schema_violation/evidence_object_missing_required",
            "schema_violation/evidence_object_invalid_type",
            "validation_failed/evidence_confidence_out_of_range",
            "schema_violation/letta_pointer_missing_required",
            "schema_violation/letta_pointer_invalid_type",
            "validation_failed/letta_pointer_hash_missing",
            "validation_failed/letta_pointer_stale_sync",
            "validation_failed/letta_agent_missing",
            "validation_failed/letta_sync_missing",
            "integration_degraded/letta_sync_failed",
            "integration_degraded/letta_stale",
            "validation_failed/letta_publish_without_gate",
            "policy_violation/letta_publish_without_governor",
            "policy_violation/letta_direct_memory_write_forbidden",
        }
        if any(code in boundary_codes for code in failure_codes):
            warnings.append("compat_mode_output_boundary_violation")
            failure_codes = [code for code in failure_codes if code not in boundary_codes]

    ok = not missing and not type_errors
    if args.strict_output_boundaries and any(
        code in {
            "schema_violation/output_payload_too_large",
            "schema_violation/output_array_too_large",
            "schema_violation/output_text_field_too_large",
            "schema_violation/evidence_object_missing_required",
            "schema_violation/evidence_object_invalid_type",
            "validation_failed/evidence_confidence_out_of_range",
            "schema_violation/letta_pointer_missing_required",
            "schema_violation/letta_pointer_invalid_type",
            "validation_failed/letta_pointer_hash_missing",
            "validation_failed/letta_pointer_stale_sync",
            "validation_failed/letta_agent_missing",
            "validation_failed/letta_sync_missing",
            "integration_degraded/letta_sync_failed",
            "integration_degraded/letta_stale",
            "validation_failed/letta_publish_without_gate",
            "policy_violation/letta_publish_without_governor",
            "policy_violation/letta_direct_memory_write_forbidden",
        }
        for code in failure_codes
    ):
        ok = False
    result = {
        "ok": ok,
        "missing_fields": sorted(set(missing)),
        "type_errors": sorted(set(type_errors)),
        "unexpected_fields": [key for key in payload.keys() if required_fields and key not in required_fields],
        "warnings": sorted(set(warnings)),
        "failure_codes": sorted(set(failure_codes)),
        "mode": "strict" if args.strict_skill_result else "compat",
        "checklist_mode": "strict" if args.strict_checklist else "compat",
        "output_boundary_mode": "strict" if args.strict_output_boundaries else "compat",
        "payload_bytes": payload_bytes,
        "limits": limits,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "output": str(args.output)}, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
