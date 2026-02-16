#!/usr/bin/env python3
"""Emit canonical episode summary and failure packet artefacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    packet = read_json(args.input)
    run_id = str(packet.get("run_id", "unknown-run"))
    task_id = str(packet.get("task_id", "unknown-task"))
    reason_codes = [str(item) for item in _as_list(packet.get("reason_codes", [])) if isinstance(item, str)]
    final_validators = _as_dict(packet.get("final_validators", {}))
    last_k_actions = _as_list(packet.get("last_k_actions", []))
    validation_gate = _as_dict(packet.get("validation_gate", {}))
    gate_passed = bool(
        packet.get(
            "gate_passed",
            validation_gate.get("all_passed", final_validators.get("all_checks_passed", False)),
        )
    )
    gate_result_ref = str(packet.get("validation_gate_result_ref", validation_gate.get("result_ref", "")))
    promoted_candidates = _as_list(packet.get("promoted_artifact_refs", []))
    promoted_artifact_refs = [item for item in promoted_candidates if isinstance(item, str)] if gate_passed else []
    checklist_timeline_ref = str(packet.get("checklist_satisfaction_timeline_ref", packet.get("checklist_timeline_ref", "")))
    progress_credit_summary = _as_dict(packet.get("progress_credit_summary", {}))
    top_contributing_actions = _as_list(packet.get("top_contributing_actions", []))
    unsatisfied_checklist_items = _as_list(packet.get("unsatisfied_checklist_items", []))
    missing_actions = [str(item) for item in _as_list(packet.get("missing_actions", [])) if isinstance(item, str)]
    trust_level = str(packet.get("trust_level", "trusted"))
    execution_profile = str(packet.get("execution_profile", ""))
    execution_audit_ref = str(packet.get("execution_audit_ref", packet.get("audit_ref", "")))
    provenance_tag = str(packet.get("provenance_tag", "real"))

    audit_reason_codes: list[str] = []
    if trust_level in {"untrusted", "generated_untrusted"}:
        if not execution_profile:
            audit_reason_codes.append("validation_failed/missing_execution_profile")
        if not execution_audit_ref:
            audit_reason_codes.append("validation_failed/missing_execution_audit_ref")
    if audit_reason_codes:
        for code in audit_reason_codes:
            if code not in reason_codes:
                reason_codes.append(code)

    relation_delta = {"should_increase_weight": [], "should_decrease_weight": []}
    if "no_progress/no_progress_loop" in reason_codes:
        relation_delta["should_decrease_weight"].append("skill-picker-orchestrator->subagent-dag-orchestrator")
    if "validation_failed/tests_not_run" in reason_codes:
        relation_delta["should_increase_weight"].append("skill-picker-orchestrator->validation-gate-runner")
    if "evidence_missing/missing_sources" in reason_codes:
        relation_delta["should_increase_weight"].append("validation-gate-runner->project-run-reporter")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    episode_path = args.output_dir / "episode_summary.json"
    failure_path = args.output_dir / "failure_packet_v2.json"
    debate_trace_path = args.output_dir / "debate_trace.json"

    episode_summary = {
        "run_id": run_id,
        "task_id": task_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_reason_codes": reason_codes,
        "last_k_actions": last_k_actions,
        "artifact_refs": [str(episode_path), str(failure_path)],
        "promoted_artifact_refs": promoted_artifact_refs,
        "promotion_gate_passed": gate_passed,
        "gate_dependencies": {
            "validation_gate_result_ref": gate_result_ref,
            "gate_owner": "validation-gate-runner",
        },
        "status": "success" if not reason_codes else "failure",
        "relation_delta": relation_delta,
        "checklist_satisfaction_timeline_ref": checklist_timeline_ref,
        "progress_credit_summary": progress_credit_summary,
        "top_contributing_actions": top_contributing_actions,
        "execution_audit": {
            "trust_level": trust_level,
            "execution_profile": execution_profile or None,
            "execution_audit_ref": execution_audit_ref or None,
            "provenance_tag": provenance_tag,
        },
    }
    failure_packet = {
        "task_id": task_id,
        "run_id": run_id,
        "final_validators": final_validators,
        "reason_codes": reason_codes,
        "last_k_actions": last_k_actions,
        "tool_errors": _as_list(packet.get("tool_errors", [])),
        "scratchpad_snapshot_ref": str(packet.get("scratchpad_snapshot_ref", "")),
        "diff_snapshot_ref": str(packet.get("diff_snapshot_ref", "")),
        "missing_actions": missing_actions,
        "unsatisfied_checklist_items": unsatisfied_checklist_items,
        "relation_delta": relation_delta,
        "gate_dependencies": {
            "validation_gate_result_ref": gate_result_ref,
            "gate_owner": "validation-gate-runner",
        },
        "promoted_artifact_refs": promoted_artifact_refs,
        "execution_audit": {
            "trust_level": trust_level,
            "execution_profile": execution_profile or None,
            "execution_audit_ref": execution_audit_ref or None,
            "provenance_tag": provenance_tag,
        },
    }

    debate_input = _as_dict(packet.get("debate_trace", {}))
    debate_trace = {
        "speaker_role": str(
            debate_input.get("speaker_role", packet.get("debate_speaker_role", ""))
        ).strip(),
        "timestamp": str(
            debate_input.get("timestamp", packet.get("debate_timestamp", datetime.now(timezone.utc).isoformat()))
        ),
        "claim_id": str(debate_input.get("claim_id", packet.get("debate_claim_id", ""))).strip(),
        "counterclaim_id": debate_input.get("counterclaim_id", packet.get("debate_counterclaim_id")),
        "evidence_refs": _as_string_list(
            debate_input.get("evidence_refs", packet.get("debate_evidence_refs", []))
        ),
    }
    debate_trace_enabled = bool(debate_trace["speaker_role"] or debate_trace["claim_id"] or debate_trace["evidence_refs"])
    if debate_trace_enabled and not debate_trace["speaker_role"]:
        audit_reason_codes.append("schema_violation/debate_trace_missing_roles")
        if "schema_violation/debate_trace_missing_roles" not in reason_codes:
            reason_codes.append("schema_violation/debate_trace_missing_roles")
    if debate_trace_enabled and not debate_trace["evidence_refs"]:
        audit_reason_codes.append("validation_failed/debate_claim_missing_evidence_ref")
        if "validation_failed/debate_claim_missing_evidence_ref" not in reason_codes:
            reason_codes.append("validation_failed/debate_claim_missing_evidence_ref")

    episode_summary["status"] = "success" if not reason_codes else "failure"

    episode_path.write_text(json.dumps(episode_summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    failure_path.write_text(json.dumps(failure_packet, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    if debate_trace_enabled:
        debate_trace_path.write_text(json.dumps(debate_trace, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    skill_ok = len(audit_reason_codes) == 0
    artefact_paths = [str(episode_path), str(failure_path)] + ([str(debate_trace_path)] if debate_trace_enabled else [])
    print(
        json.dumps(
            {
                "episode_summary_path": str(episode_path),
                "failure_packet_path": str(failure_path),
                "debate_trace_path": str(debate_trace_path) if debate_trace_enabled else "",
                "episode_summary": episode_summary,
                "skill_result": {
                    "ok": skill_ok,
                    "outputs": {
                        "episode_summary": episode_summary,
                        "failure_packet_path": str(failure_path),
                        "debate_trace_path": str(debate_trace_path) if debate_trace_enabled else "",
                    },
                    "tool_calls": [{"tool_name": "emit_episode_log", "params_hash": run_id, "duration_ms": 0.0}],
                    "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
                    "artefact_delta": {
                        "files_changed": artefact_paths,
                        "tests_run": [],
                        "urls_fetched": [],
                    },
                    "progress_proxy": {
                        "reason_code_count": len(reason_codes),
                        "top_contributing_actions_count": len(top_contributing_actions),
                    },
                    "failure_codes": audit_reason_codes,
                    "suggested_next": [] if skill_ok else ["attach_execution_audit_fields"],
                    "episode_summary": episode_summary,
                    "final_reason_codes": reason_codes,
                    "last_k_actions": last_k_actions,
                    "artifact_refs": artefact_paths,
                    "reason_codes": reason_codes,
                },
            },
            ensure_ascii=True,
        )
    )
    return 0 if skill_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
