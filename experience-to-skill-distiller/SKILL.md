---
name: experience-to-skill-distiller
description: Distil experience and failure packets into candidate skill updates with failure lessons.
---

# Experience To Skill Distiller

## Purpose

Distil experience and failure packets into candidate skill updates with failure lessons.

## Workflow

1. Validate inputs and required artefact references.
2. Run deterministic transform/evaluation logic.
3. Emit structured output artefacts for downstream skills.
4. Fail closed if schema, evidence, or budget requirements are missing.

## Output Contract

- `output/experience-to-skill-distiller/result.json`
- `output/experience-to-skill-distiller/memory_design_candidate.json` (proposal-only candidate packet)

`memory_design_candidate` minimum fields:
- `source_run_id`
- `eval_task_ids[]`
- `artefact_refs[]`
- `interface_compliant`

Fail-closed:
- emit `schema_violation/memory_design_missing_interface` when required interface fields are missing.
- emit `policy_violation/memory_design_forbidden_io` when forbidden I/O is detected in candidate generation.

## Command Pattern

```bash
python3 scripts/run_experience_to_skill_distiller.py --input /tmp/input.json --output /tmp/output.json
```

```bash
python3 scripts/emit_memory_design_candidate.py --input /tmp/candidate_input.json --output /tmp/memory_design_candidate.json
```

## Interdependent Skills

- Used by `skill-picker-orchestrator`, `rlm-repl-runtime`, and `project-run-reporter` in memory-aware flows.
- Output contracts are consumed by `validation-gate-runner` and `skillbank-store-versioning` where applicable.

## Standard SkillResult Telemetry

Every skill must emit a `SkillResult` envelope (or expose equivalent data for the harness adapter):
- `ok`
- `outputs`
- `tool_calls`
- `cost_units`
- `artefact_delta`
- `progress_proxy`
- `failure_codes`
- `suggested_next`

Compatibility phase:
- Legacy outputs are accepted when wrapped by the central harness adapter.

Strict phase:
- Missing or malformed `SkillResult` fails closed via `tool-contract-enforcer`.

## Tier 3 Learning Telemetry

Learning/memory skills must ingest failure packets and emit trace-linked lessons:
- include before/after state sizes or hashes
- include archived IDs for stored units
- include linkage back to `run_id` and failure evidence refs
