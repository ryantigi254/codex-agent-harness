# Architecture Overview

Canonical map:
- `diagram.mmd`

Focused slice views:
- `diagram.control-plane.mmd`
- `diagram.evidence-gates.mmd`
- `diagram.learning-memory.mmd`

## Sufficiency gate overlays
- 20-task checkpoint is a governance overlay, not runtime mutation.
- Scorecard contract: `harness_task_scorecard`.
- Checkpoint contract: `harness_sufficiency_checkpoint`.
- Deterministic go/no-go script consumes scorecards and emits checkpoint summaries.
