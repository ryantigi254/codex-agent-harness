#!/usr/bin/env python3
"""Stage Letta draft memory packets locally for gated publish."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

DRAFT_ROOT = Path('/Users/ryangichuru/.codex/skills/.cache/letta/drafts')


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('input must be object')
    return payload


def _normalise_draft(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'source_pointers': [str(v) for v in _as_list(item.get('source_pointers', [])) if str(v).strip()],
        'summary': str(item.get('summary', '')).strip(),
        'provenance_tag': str(item.get('provenance_tag', 'real')).strip() or 'real',
        'created_at_unix': int(item.get('created_at_unix', int(time.time()))),
        'confidence': float(item.get('confidence', 0.5)),
        'thread_id': str(item.get('thread_id', '')).strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--draft-root', type=Path, default=DRAFT_ROOT)
    args = parser.parse_args()

    payload = _read_json(args.input)
    run_id = str(payload.get('run_id', '')).strip()
    agent_id = str(payload.get('agent_id', '')).strip()
    project_id = str(payload.get('project_id', '')).strip()
    drafts_in = _as_list(payload.get('drafts', []))

    reason_codes: list[str] = []
    if not run_id or not agent_id or not project_id:
        reason_codes.append('schema_violation/malformed_payload')

    drafts: list[dict[str, Any]] = []
    for item in drafts_in:
        if not isinstance(item, dict):
            reason_codes.append('schema_violation/malformed_payload')
            continue
        draft = _normalise_draft(item)
        if not draft['source_pointers'] or not draft['summary']:
            reason_codes.append('schema_violation/malformed_payload')
            continue
        drafts.append(draft)

    if not drafts:
        reason_codes.append('validation_failed/tests_not_run')

    queue_path = args.draft_root / f'{run_id}.json'
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    queue: dict[str, Any] = {'run_id': run_id, 'agent_id': agent_id, 'project_id': project_id, 'drafts': []}
    if queue_path.exists():
        try:
            current = json.loads(queue_path.read_text(encoding='utf-8'))
            if isinstance(current, dict):
                queue = current
        except Exception:
            pass

    queue.setdefault('run_id', run_id)
    queue.setdefault('agent_id', agent_id)
    queue.setdefault('project_id', project_id)
    queue.setdefault('drafts', [])
    if isinstance(queue['drafts'], list):
        queue['drafts'].extend(drafts)

    ok = len(reason_codes) == 0
    if ok:
        queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')

    result = {
        'ok': ok,
        'reason_codes': sorted(set(reason_codes)),
        'draft_queue_ref': str(queue_path),
        'draft_count': len(queue.get('drafts', [])) if isinstance(queue.get('drafts'), list) else 0,
        'skill_result': {
            'ok': ok,
            'outputs': {
                'draft_queue_ref': str(queue_path),
                'draft_count': len(queue.get('drafts', [])) if isinstance(queue.get('drafts'), list) else 0,
            },
            'tool_calls': [{'tool_name': 'stage_letta_draft', 'params_hash': run_id or 'none', 'duration_ms': 0.0}],
            'cost_units': {'time_ms': 0.0, 'tokens': 0, 'cost_estimate': 0.0, 'risk_class': 'low'},
            'artefact_delta': {'files_changed': [str(queue_path)] if ok else [], 'files_created': [str(queue_path)] if ok else [], 'tests_run': [], 'urls_fetched': [], 'screenshots': []},
            'progress_proxy': {'draft_count': len(queue.get('drafts', [])) if isinstance(queue.get('drafts'), list) else 0},
            'failure_codes': sorted(set(reason_codes)),
            'suggested_next': ['publish_letta_drafts'] if ok else ['repair_letta_draft_payload'],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
