#!/usr/bin/env python3
"""Emit structured experience packet for distillation and memory reflection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalise_external_context_refs(packet: dict[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get('external_context_refs', packet.get('external_context_pointers', []))
    if not isinstance(raw, list):
        return []
    refs: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                'document_id': str(item.get('document_id', '')),
                'source_uri': str(item.get('source_uri', '')),
                'content_hash': str(item.get('content_hash', '')),
            }
        )
    return refs


def _normalise_external_context_pointers(packet: dict[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get('external_context_pointers', packet.get('external_context_refs', []))
    if not isinstance(raw, list):
        return []
    pointers: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pointers.append(
            {
                'provider': str(item.get('provider', 'letta')),
                'folder_id': str(item.get('folder_id', '')),
                'document_id': str(item.get('document_id', '')),
                'source_uri': str(item.get('source_uri', '')),
                'content_hash': str(item.get('content_hash', '')),
                'synced_at_unix': int(item.get('synced_at_unix', 0)) if str(item.get('synced_at_unix', '')).strip() else 0,
                'provenance_tag': str(item.get('provenance_tag', 'real')),
                'project_id': str(item.get('project_id', '')),
                'thread_id': str(item.get('thread_id', '')),
            }
        )
    return pointers


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('input must be object')
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()

    packet = read_json(args.input)
    run_id = str(packet.get('run_id', 'unknown-run'))
    experience_packet = {
        'run_id': run_id,
        'task_signature': str(packet.get('task_signature', packet.get('task_id', 'unknown-task'))),
        'skills_used': _as_list(packet.get('skills_used', packet.get('skill_stack_used', []))),
        'gate_failures': _as_list(packet.get('gate_failures', packet.get('reason_codes', []))),
        'key_decisions': _as_list(packet.get('key_decisions', packet.get('last_k_actions', []))),
        'evidence_pointers': _as_list(packet.get('evidence_pointers', packet.get('artifact_refs', []))),
        'final_outcome': str(packet.get('final_outcome', 'success' if not _as_list(packet.get('reason_codes', [])) else 'failure')),
        'trajectory_ref': str(packet.get('trajectory_ref', '')),
        'failure_packet_ref': str(packet.get('failure_packet_ref', '')),
        'checklist_timeline_ref': str(packet.get('checklist_timeline_ref', packet.get('checklist_satisfaction_timeline_ref', ''))),
        'external_context_refs': _normalise_external_context_refs(packet),
        'external_context_pointers': _normalise_external_context_pointers(packet),
    }

    missing = []
    list_can_be_empty = {"gate_failures"}
    for key in ['task_signature', 'skills_used', 'gate_failures', 'key_decisions', 'evidence_pointers', 'final_outcome']:
        value = experience_packet.get(key)
        if value == "":
            missing.append(key)
        if value == [] and key not in list_can_be_empty:
            missing.append(key)
    ok = len(missing) == 0
    out = {
        'ok': ok,
        'missing_fields': missing,
        'experience_packet': experience_packet,
        'skill_result': {
            'ok': ok,
            'outputs': {'experience_packet_path': str(args.output), 'run_id': run_id},
            'tool_calls': [{'tool_name': 'emit_experience_packet', 'params_hash': run_id, 'duration_ms': 0.0}],
            'cost_units': {'time_ms': 0.0, 'tokens': 0, 'cost_estimate': 0.0, 'risk_class': 'low'},
            'artefact_delta': {'files_changed': [str(args.output)], 'files_created': [str(args.output)], 'tests_run': [], 'urls_fetched': [], 'screenshots': []},
            'progress_proxy': {'field_count': len(experience_packet)},
            'failure_codes': ['schema_violation/experience_packet_missing_required'] if not ok else [],
            'suggested_next': ['scratchpad-governor'] if ok else ['repair_experience_packet'],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
