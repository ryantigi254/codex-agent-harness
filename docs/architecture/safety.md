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
- Governor merge decisions happen only after validator gates pass.

## Reward anti-gaming
- Reward is outcome-per-cost only.
- Reward cannot be increased by activity volume (more skill calls, more traces, more memory writes).
- Positive progress is valid only when validator improvement is true.
