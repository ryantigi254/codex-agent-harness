---
name: tool-contract-enforcer
description: Enforce strict schema and fail-closed checks for tool and subagent outputs.
---

# Tool Contract Enforcer

## Purpose

Validate output contracts for runtime helpers, subagents, and memory interfaces before merge.

## Workflow

1. Validate payload against required keys and optional nested type constraints.
2. Reject unknown critical fields when strict mode is enabled.
3. Emit pass/fail report with deterministic error list.
4. Fail closed on contract mismatch.
5. For synthetic trajectories with tool invocations, enforce strict tool-call schema matching.

## Output Contract

- `output/tool-contract-enforcer/contract_report.json`
- `output/tool-contract-enforcer/result.json`
- deterministic policy failures should include:
  - `schema_violation/synthetic_tool_call_invalid`

## Command Pattern

```bash
python3 scripts/run_tool_contract_enforcer.py --input /tmp/input.json --output /tmp/output.json
```

## Interdependent Skills

- Called by `validation-gate-runner` for machine-checkable contract enforcement.
- Used by `subagent-dag-orchestrator` for worker handoff schema checks.
- Used by `memory-backend-adapter` and `memory-design-interface` for schema compatibility checks.

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
