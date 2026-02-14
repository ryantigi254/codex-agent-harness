# Safety

Grounding and validation gates must pass before final output publication.

## Hard safety gates
- Acceptance truth is `ValidatorResult`, not free-text narrative.
- Boundary payload caps are enforced before outputs are accepted.
- Evidence references must use typed `EvidenceObject` payloads.

## Merge safety
- Subagents never merge directly to main memory.
- Subagents submit proposals only.
- subagents propose diffs before governor review.
- only governor can merge after validator gates pass.
- merge-authority audits are strict and direct subagent merge is zero-tolerance.

## Opportunistic resume safety
- `opportunistic_resume_checkpoint` links context memory state to candidate next work.
- `governor_gate_state=ready` requires non-empty candidate next work items.

## Sufficiency gate classification
A run is marked `harness_plumbing_change_required=true` only when failure root cause requires contract/policy/harness logic edits. Skill logic, runbook content, or evaluation content changes do not count as harness plumbing.

## Reward anti-gaming
- Reward is outcome-per-cost only.
- Reward cannot be increased by activity volume (more skill calls, more traces, more memory writes).
- Positive progress is valid only when validator-improving progress is true.
