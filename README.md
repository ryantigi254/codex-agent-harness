# Codex Agent Harness

A reusable harness for orchestrating agent skills with evidence-first execution, explicit gates, and artifact-backed state.

## Design principles
- Evidence first: collect and attach evidence objects before claims are accepted.
- Gated outputs: validator and grounding gates must pass before final outputs.
- Artifact-backed state: traces, reports, and screenshots are persisted and referenced.
- Strict contracts: every boundary crossing is typed and fail-closed in CI.

## Quickstart
1. Add a skill:
   - Register it in `harness/skills/registry.json`.
   - Point to input/output schemas in `harness/skills/schemas/`.
2. Run a runbook:
   - Add workflow files under `runbooks/examples/` or `runbooks/checks/`.
3. Validate:
   - Run `./scripts/validate_repo.sh`.
   - Run `python3 ./scripts/validate_contracts.py --strict`.

## Repo map
- `docs/architecture/`: diagram and architecture contracts/routing/memory/safety/evals docs.
- `harness/skills/registry.json`: source of truth for skill metadata and contracts.
- `harness/skills/schemas/`: JSON schema contracts for stable skill I/O.
- `runbooks/`: repeatable execution workflows.
- `scripts/`: repo automation and validation scripts.
- `examples/`: minimal end-to-end examples.

## Strict v2 contract set
- `SkillResult`: `harness/skills/schemas/skill_result.schema.json`
- `EvidenceObject`: `harness/skills/schemas/evidence_object.schema.json`
- `ValidatorResult`: `harness/skills/schemas/validator_result.schema.json`
- `ExperiencePacket`: `harness/skills/schemas/experience_packet.schema.json`
- Output boundaries: `harness/skills/schemas/output_boundaries.schema.json`
- Merge authority policy: `harness/skills/schemas/merge_authority_policy.schema.json`
- Reward policy: `harness/skills/schemas/reward_policy.schema.json`

## Governance hard rules
- Subagents propose diffs only; only governor can merge after validator gates.
- Positive reward requires validator-improving progress and cost-bounded outcomes.
- Activity-volume rewards are forbidden (`skill_count_bonus` style terms fail policy checks).

## CI gate matrix
- `contracts-lint`: registry and schema lint.
- `contracts-validate-strict`: strict contract and fixture validation.
- `policy-gates`: merge-authority and reward anti-gaming checks.
- `docs-consistency`: docs must match strict v2 governance semantics.
