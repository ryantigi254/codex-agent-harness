#!/usr/bin/env python3
"""Write a durable memory entry into the git-backed context repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

MEMORY_REPO = Path('/Users/ryangichuru/.codex/skills/memory_repo')
VALID_SCOPES = {'system', 'domain', 'tasks', 'ops'}
LETTA_REQUIRED_FIELDS = {
    'provider',
    'folder_id',
    'document_id',
    'source_uri',
    'content_hash',
    'synced_at_unix',
    'provenance_tag',
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('input must be object')
    return payload


def _slug(text: str) -> str:
    base = ''.join(ch.lower() if ch.isalnum() else '-' for ch in text).strip('-')
    return '-'.join(part for part in base.split('-') if part)[:80] or 'entry'


def _validate_external_context_pointers(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    reason_codes: list[str] = []
    if raw is None:
        return [], reason_codes
    if not isinstance(raw, list):
        return [], ['schema_violation/letta_pointer_invalid_type']
    pointers: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            reason_codes.append('schema_violation/letta_pointer_invalid_type')
            continue
        missing = [key for key in LETTA_REQUIRED_FIELDS if key not in item]
        if missing:
            reason_codes.append('schema_violation/letta_pointer_missing_required')
        if item.get('provider') not in (None, 'letta'):
            reason_codes.append('schema_violation/letta_pointer_invalid_type')
        if not str(item.get('content_hash', '')).strip():
            reason_codes.append('validation_failed/letta_pointer_hash_missing')
        synced_at = item.get('synced_at_unix')
        if synced_at is not None and not isinstance(synced_at, (int, float)):
            reason_codes.append('schema_violation/letta_pointer_invalid_type')
        elif isinstance(synced_at, (int, float)) and float(synced_at) <= 0:
            reason_codes.append('validation_failed/letta_pointer_stale_sync')
        if item.get('stale', False) is True or item.get('is_stale', False) is True:
            reason_codes.append('validation_failed/letta_pointer_stale_sync')
        pointers.append(item)
    return pointers, sorted(set(reason_codes))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--repo-root', type=Path, default=MEMORY_REPO)
    parser.add_argument('--no-commit', action='store_true')
    args = parser.parse_args()

    payload = _read_json(args.input)
    run_id = str(payload.get('run_id', 'unknown-run'))
    title = str(payload.get('title', '')).strip()
    when_to_use = str(payload.get('when_to_use', '')).strip()
    scope = str(payload.get('scope', 'tasks')).strip()
    source_pointers = payload.get('source_pointers', []) if isinstance(payload.get('source_pointers', []), list) else []
    external_context_pointers_raw = payload.get('external_context_pointers', payload.get('published_letta_pointers', []))
    external_context_pointers, pointer_errors = _validate_external_context_pointers(external_context_pointers_raw)
    summary_lines = payload.get('summary_lines', []) if isinstance(payload.get('summary_lines', []), list) else []

    reason_codes: list[str] = []
    if not title:
        reason_codes.append('schema_violation/context_repo_frontmatter_missing')
    if not when_to_use:
        reason_codes.append('schema_violation/context_repo_frontmatter_missing')
    if scope not in VALID_SCOPES:
        reason_codes.append('schema_violation/context_repo_invalid_layout')
    if not source_pointers:
        reason_codes.append('validation_failed/memory_provenance_missing')
    reason_codes.extend(pointer_errors)
    if bool(payload.get('direct_external_memory_write', False)) or bool(payload.get('external_memory_write_committed', False)):
        reason_codes.append('policy_violation/letta_direct_memory_write_forbidden')
    if reason_codes:
        result = {'ok': False, 'reason_codes': sorted(set(reason_codes)), 'skill_result': {'ok': False, 'outputs': {}, 'tool_calls': [], 'cost_units': {'time_ms': 0.0}, 'artefact_delta': {'files_changed': []}, 'progress_proxy': None, 'failure_codes': sorted(set(reason_codes)), 'suggested_next': ['repair_memory_entry_payload']}}
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=True))
        return 2

    repo_root = args.repo_root
    scope_dir = repo_root / scope
    scope_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{title}|{run_id}".encode('utf-8')).hexdigest()[:10]
    rel_path = Path(scope) / f"{_slug(title)}-{digest}.md"
    out_path = repo_root / rel_path

    frontmatter = [
        '---',
        f'title: "{title}"',
        f'when_to_use: "{when_to_use}"',
        f'scope: "{scope}"',
        'source_pointers:'
    ] + [f'  - "{str(item)}"' for item in source_pointers] + ['---', '']

    if external_context_pointers:
        external_block = ['external_context_pointers:']
        for pointer in external_context_pointers:
            external_block.extend(
                [
                    f'  - provider: "{str(pointer.get("provider", "letta"))}"',
                    f'    folder_id: "{str(pointer.get("folder_id", ""))}"',
                    f'    document_id: "{str(pointer.get("document_id", ""))}"',
                    f'    source_uri: "{str(pointer.get("source_uri", ""))}"',
                    f'    content_hash: "{str(pointer.get("content_hash", ""))}"',
                    f'    synced_at_unix: {int(pointer.get("synced_at_unix", 0))}',
                    f'    provenance_tag: "{str(pointer.get("provenance_tag", "real"))}"',
                ]
            )
            if pointer.get('namespace'):
                external_block.append(f'    namespace: "{str(pointer.get("namespace"))}"')
            if pointer.get('retrieval_hint'):
                external_block.append(f'    retrieval_hint: "{str(pointer.get("retrieval_hint"))}"')
            if pointer.get('sync_job_ref'):
                external_block.append(f'    sync_job_ref: "{str(pointer.get("sync_job_ref"))}"')
            if pointer.get('notes_ref'):
                external_block.append(f'    notes_ref: "{str(pointer.get("notes_ref"))}"')
        frontmatter = frontmatter[:-2] + external_block + ['---', '']

    body = ['# Summary'] + [f'- {str(line)}' for line in summary_lines[:10]]
    if len(body) == 1:
        body.append('- durable lesson recorded from run artefacts')

    out_path.write_text('\n'.join(frontmatter + body) + '\n', encoding='utf-8')

    commit_hash = ''
    if not args.no_commit:
        subprocess.run(['git', '-C', str(repo_root), 'add', str(rel_path)], check=False, capture_output=True, text=True)
        message = f"memory: add {scope} entry from {run_id}"
        commit = subprocess.run(['git', '-C', str(repo_root), 'commit', '-m', message], check=False, capture_output=True, text=True)
        if commit.returncode == 0:
            head = subprocess.run(['git', '-C', str(repo_root), 'rev-parse', 'HEAD'], check=False, capture_output=True, text=True)
            commit_hash = head.stdout.strip() if head.returncode == 0 else ''

    result = {
        'ok': True,
        'entry_path': str(out_path),
        'entry_rel_path': str(rel_path),
        'commit_hash': commit_hash,
        'run_id': run_id,
        'external_context_pointer_count': len(external_context_pointers),
        'skill_result': {
            'ok': True,
            'outputs': {
                'entry_path': str(out_path),
                'commit_hash': commit_hash,
                'run_id': run_id,
                'external_context_pointer_count': len(external_context_pointers),
            },
            'tool_calls': [{'tool_name': 'write_memory_repo_entry', 'params_hash': digest, 'duration_ms': 0.0}],
            'cost_units': {'time_ms': 0.0, 'tokens': 0, 'cost_estimate': 0.0, 'risk_class': 'low'},
            'artefact_delta': {'files_changed': [str(out_path)], 'files_created': [str(out_path)], 'tests_run': [], 'urls_fetched': [], 'screenshots': []},
            'progress_proxy': {'memory_entries_written': 1},
            'failure_codes': [],
            'suggested_next': ['validation-gate-runner'],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
