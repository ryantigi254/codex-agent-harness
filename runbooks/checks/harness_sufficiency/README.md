# Harness Sufficiency Checkpoint

This pack defines the fixed 20-task checkpoint for deciding when harness updates are no longer justified by measured failures.

## Task pack
- Source: `task_pack_v1.json`
- Distribution: 5 tasks each for:
  - `research_pdf`
  - `repo_change`
  - `deploy_flow`
  - `long_form_factual`

## Outputs
- Scorecards: `runbooks/checks/harness_sufficiency/scorecards/<checkpoint_id>/`
- Checkpoint summary: `runbooks/checks/harness_sufficiency/checkpoints/<checkpoint_id>.json`

## Go / no-go rule
- `go` only when:
  - harness plumbing changes `<=3/20`
  - all six stability criteria pass
- else `no_go` with explicit failed conditions and recommended actions.
