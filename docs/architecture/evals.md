# Evals

Runbooks and examples provide repeatable checks for orchestration and contract compliance.

## CI hard gates
- `contracts-lint`
- `contracts-validate-strict`
- `policy-gates`
- `docs-consistency`

Any single failure blocks the workflow.

## Deterministic fixture checks
- Pass fixtures in `examples/contracts/pass/` must validate with zero errors.
- Fail fixtures in `examples/contracts/fail/` must fail with expected deterministic error keys.

## Summary lines for monitoring
- contracts passed/failed count
- policy violations count
- boundary violations count
