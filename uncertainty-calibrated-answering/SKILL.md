---
name: uncertainty-calibrated-answering
description: Use only when the user explicitly asks for feature suggestions or feature additions for any project. Produce confidence-calibrated feature recommendations, call out assumptions, and abstain on weakly supported ideas.
---

# Uncertainty-Calibrated Answering

## Trigger
- Use this skill only when the request is about feature ideas, feature suggestions, or feature additions.
- Do not use it for bug fixes, refactors, or implementation-only tasks unless the user explicitly asks for feature options.

## Workflow
1. Extract product context, constraints, and target user outcome from the prompt/repo.
2. Generate candidate features with explicit rationale tied to the stated outcome.
3. Assign confidence tiers for each feature:
   - High: strongly supported by context/evidence.
   - Medium: plausible but needs one missing assumption.
   - Low: speculative; mark as uncertain.
4. For medium/low items, list missing evidence needed to raise confidence.
5. Rank by value-to-complexity and expected regression risk.
6. If confidence is low across all options, abstain from hard recommendations and return the minimum context required.

## Output Contract
- Return a concise table with columns:
  - `Feature`
  - `Why now`
  - `Confidence`
  - `Risk`
  - `Evidence missing`
- Keep speculative ideas explicitly labelled as `Speculation`.
- For any multi-model escalation path, emit `output/uncertainty-calibrated-answering/routing_decision_packet.json` with:
  - `step_id`
  - `candidate_models[]`
  - `chosen_model`
  - `confidence`
  - `budget_state`
  - `justification_code`

Fail-closed:
- emit `schema_violation/routing_packet_missing` when multi-model routing occurs without a routing packet.

Command pattern:

```bash
python3 scripts/emit_routing_decision_packet.py --input /tmp/routing_step.json --output /tmp/routing_decision_packet.json
```

## Interdependent Skills
- Use with [`logic-chain-task-planner`](/Users/ryangichuru/.codex/skills/logic-chain-task-planner/SKILL.md) to convert selected features into implementable execution chains.
- Use with [`plan-validator-symbolic`](/Users/ryangichuru/.codex/skills/plan-validator-symbolic/SKILL.md) before implementation if the feature has strict state transitions or ordering constraints.

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

## Tier 2 Reason-Code Normalisation

Guardrail outputs must expose machine-readable policy telemetry:
- `risk_class`
- `policy_decision` (`allow|block|needs_evidence`)
- `violations[]`
- `reason_codes[]` mapped to `missing_actions[]` in failure packets

These fields guide central reward penalties and mistake-learning updates; do not compute local reward here.
