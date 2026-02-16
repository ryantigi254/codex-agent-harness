# Context Repo Contract

Durable project memory is stored in a git-backed context repository at:

`/Users/ryangichuru/.codex/skills/memory_repo`

## Layout

- `system/`: pinned always-loaded rules (short, high-signal)
- `domain/`: domain-specific durable lessons
- `tasks/`: task-shape guidance and repeated patterns
- `ops/`: operational runbooks and diagnostics
- `.meta/`: templates and governance metadata

## Frontmatter

Every memory file must include:

- `title`
- `when_to_use`
- `scope` (`system|domain|tasks|ops`)
- `source_pointers` (non-empty)

## Governance

- `scratchpad-governor` is the only merge authority.
- Subagents may edit memory only in isolated worktrees for `memory_write` tasks.
- `validation-gate-runner` validates schema/provenance/commit hygiene before merge.
- Scratchpad stores pointers to memory files, not large durable bodies.
- External context provider mode is `read_only_mirror` with authority fixed to `git_memory_repo`.
- Direct external writes into durable memory are forbidden and fail closed with `policy_violation/letta_direct_memory_write_forbidden`.
- Runtime retrieval uses a hybrid model: Letta mirror preflight plus local `memory_repo` retrieval.
- Letta runtime failures are fail-open to local retrieval with degraded telemetry reason codes.

## External Context Pointers

When a memory entry links external Letta context, frontmatter may include `external_context_pointers` with strong metadata:

- `provider` (`letta`)
- `folder_id`
- `document_id`
- `source_uri`
- `content_hash`
- `synced_at_unix`
- `provenance_tag` (`real|simulated`)

## Runtime Sync and Publish

- Per-task preflight sync is bounded by TTL cache under `/Users/ryangichuru/.codex/skills/.cache/letta/<agent_id>/`.
- Draft learning writes to local queue first at `/Users/ryangichuru/.codex/skills/.cache/letta/drafts/<run_id>.json`.
- Publish to Letta is gated:
  - `validator_passed=true`
  - `governor_approved=true`
- Publish without gate/governor fails closed with:
  - `validation_failed/letta_publish_without_gate`
  - `policy_violation/letta_publish_without_governor`

## Related Schemas

- `/Users/ryangichuru/.codex/skills/scripts/context_repo_contract_schema.json`
- `/Users/ryangichuru/.codex/skills/scripts/memory_file_frontmatter_schema.json`
- `/Users/ryangichuru/.codex/skills/scripts/memory_update_bundle_schema.json`
- `/Users/ryangichuru/.codex/skills/scripts/letta_pointer_contract_schema.json`
