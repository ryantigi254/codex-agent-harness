#!/usr/bin/env python3
"""Publish staged Letta drafts after validator/governor approval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path('/Users/ryangichuru/.codex/skills/scripts')
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from letta_adapter import publish_drafts  # type: ignore


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('input must be object')
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()

    payload = _read_json(args.input)
    run_id = str(payload.get('run_id', '')).strip()
    draft_queue_ref = Path(str(payload.get('draft_queue_ref', '')).strip()) if payload.get('draft_queue_ref') else None

    if not run_id:
        result = {'ok': False, 'reason_codes': ['validation_failed/letta_publish_without_gate'], 'external_context_pointers': []}
    else:
        queue_payload: dict[str, Any] = {}
        if draft_queue_ref and draft_queue_ref.exists():
            try:
                loaded = json.loads(draft_queue_ref.read_text(encoding='utf-8'))
                if isinstance(loaded, dict):
                    queue_payload = loaded
            except Exception:
                queue_payload = {}
        publish_input: dict[str, Any] = dict(payload)
        publish_input['run_id'] = run_id
        publish_input['drafts'] = queue_payload.get('drafts', []) if isinstance(queue_payload.get('drafts', []), list) else []
        publish_input['agent_id'] = str(payload.get('agent_id', queue_payload.get('agent_id', '')))
        publish_input['project_id'] = str(payload.get('project_id', queue_payload.get('project_id', '')))
        result = publish_drafts(publish_input)

    out = {
        'ok': bool(result.get('ok', False)),
        'reason_codes': result.get('reason_codes', []),
        'external_context_pointers': result.get('external_context_pointers', []),
        'published_count': int(result.get('published_count', 0)),
        'skill_result': {
            'ok': bool(result.get('ok', False)),
            'outputs': {
                'published_count': int(result.get('published_count', 0)),
                'external_context_pointer_count': len(result.get('external_context_pointers', [])) if isinstance(result.get('external_context_pointers', []), list) else 0,
            },
            'tool_calls': [{'tool_name': 'publish_letta_drafts', 'params_hash': run_id or 'none', 'duration_ms': 0.0}],
            'cost_units': {'time_ms': 0.0, 'tokens': 0, 'cost_estimate': 0.0, 'risk_class': 'low'},
            'artefact_delta': {'files_changed': [], 'files_created': [], 'tests_run': [], 'urls_fetched': [], 'screenshots': []},
            'progress_proxy': {'published_count': int(result.get('published_count', 0))},
            'failure_codes': result.get('reason_codes', []),
            'suggested_next': ['write_memory_repo_entry'] if bool(result.get('ok', False)) else ['repair_publish_preconditions'],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=True))
    return 0 if out['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
