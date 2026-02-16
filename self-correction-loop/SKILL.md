---
name: self-correction-loop
description: Use during execution/debugging to iteratively compare expected vs observed results, update hypotheses, and pick the next corrective action.
---

# Self Correction Loop

## Trigger
- Use when a task is being executed in steps and outcomes can diverge.
- Use when debugging stalls and hypothesis updates are needed.

## Loop
1. Record expected outcome for the current step.
2. Observe actual result from command/test/output.
3. Classify mismatch:
   - Assumption error
   - Implementation error
   - Environment/config error
   - Data/input error
4. Update hypothesis and choose the smallest next corrective step.
5. Re-test narrowly, then widen validation after a pass.
6. Enforce a bounded edit-pass budget and stop on non-improving validator delta.

## Output Contract
- Keep a compact loop log per cycle:
  - `Expected`
  - `Observed`
  - `Mismatch class`
  - `Next action`
  - `Validation result`
- Emit `output/self-correction-loop/edit_trace.json` with:
  - `pass_index`
  - `before_hash`
  - `after_hash`
  - `validator_delta`
  - `stop_reason`

Fail-closed:
- `validation_failed/edit_pass_non_improving`
- `validation_failed/edit_loop_exceeded_budget`
- `validation_failed/edit_oscillation_detected`

Command pattern:

```bash
python3 scripts/emit_edit_trace.py --input /tmp/edit_step.json --output /tmp/edit_trace.json
```

## Interdependent Skills
- Commonly follows [`plan-validator-symbolic`](/Users/ryangichuru/.codex/skills/plan-validator-symbolic/SKILL.md).
- Pair with [`regression-pattern-hunter`](/Users/ryangichuru/.codex/skills/regression-pattern-hunter/SKILL.md) once the immediate defect is fixed.

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

## Tier 4 Planning Telemetry

Planning/helper outputs should include structured decision metadata:
- `decision`
- `confidence`
- `assumptions`
- `quality_proxy`

Do not define reward logic inside helper skills.
