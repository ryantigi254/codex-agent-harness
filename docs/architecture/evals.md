# Evals

Runbooks and examples provide repeatable checks for orchestration and contract compliance.

## 20-task checkpoint procedure
1. Run task pack: `runbooks/checks/harness_sufficiency/task_pack_v1.json`.
2. Produce one `harness_task_scorecard` per run.
3. Aggregate with `scripts/run_harness_checkpoint.py`.
4. Commit scorecards and checkpoint JSON for review.

## Class matrix
- `research_pdf`: 5
- `repo_change`: 5
- `deploy_flow`: 5
- `long_form_factual`: 5

## Go/no-go semantics
- `go`: plumbing changes `<=3/20` and all six stability criteria pass.
- `no_go`: any stability criterion fails or plumbing changes exceed threshold.
- Escalation: map every no-go condition to a recurring measured failure mode before any harness edit.

## CI hard gates
- `contracts-lint`
- `contracts-validate-strict`
- `policy-gates`
- `regression-pack`
- `json-render-smoke`
- `checkpoint-contracts`
- `checkpoint-regression-pack`
- `checkpoint-go-no-go-script`
- `docs-consistency`

Any single failure blocks the workflow.

## Deterministic checks
- pass fixtures in `examples/contracts/pass/` must validate with zero errors.
- fail fixtures in `examples/contracts/fail/` must fail with expected deterministic reason keys.
- fuzz fixtures in `examples/contracts/fuzz/` must fail with expected deterministic reason keys.
- regression packs assert stable reason-code outcomes.

## Summary lines for monitoring
- `contracts_checked`
- `registry_coverage_failures`
- `fuzz_cases_passed/failed`
- `merge_audit_violations`
- `checkpoint_contract_violations`
- `reason_code_drift_failures`
- `checkpoint_runs_count`
- `checkpoint_go_count`
- `checkpoint_no_go_count`
- `missing_stability_proof_count`
