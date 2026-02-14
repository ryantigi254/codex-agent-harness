# Codex Agent Harness

A reusable harness for orchestrating agent skills with evidence-first execution, explicit gates, and artifact-backed state.

## Design principles
- Evidence first: collect and attach evidence objects before claims are accepted.
- Gated outputs: validator and grounding gates must pass before final outputs.
- Artifact-backed state: traces, reports, and screenshots are persisted and referenced.

## Quickstart
1. Add a skill:
   - Register it in `harness/skills/registry.json`.
   - Point to input/output schemas in `harness/skills/schemas/`.
2. Run a runbook:
   - Add workflow files under `runbooks/examples/` or `runbooks/checks/`.
3. Validate:
   - Run `./scripts/validate_repo.sh`.

## Repo map
- `docs/architecture/`: diagram and architecture contracts/routing/memory/safety/evals docs.
- `harness/skills/registry.json`: source of truth for skill metadata and contracts.
- `harness/skills/schemas/`: JSON schema contracts for stable skill I/O.
- `runbooks/`: repeatable execution workflows.
- `scripts/`: repo automation and validation scripts.
- `examples/`: minimal end-to-end examples.
