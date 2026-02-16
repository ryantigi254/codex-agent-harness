# Codex Agent Harness

A reusable harness for orchestrating agent skills with evidence-first execution, explicit gates, and artefact-backed state.

## Design principles
- Evidence first: collect and attach evidence objects before claims are accepted.
- Gated outputs: validator and grounding gates must pass before final outputs.
- Artefact-backed state: traces, reports, and screenshots are persisted and referenced.
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

## 20-task sufficiency gate
- Fixed matrix: `runbooks/checks/harness_sufficiency/task_pack_v1.json` (5 tasks per class, 20 total).
- Per-run scorecards: `harness_task_scorecard`.
- Checkpoint aggregate: `harness_sufficiency_checkpoint`.
- Go/no-go threshold:
  - harness plumbing changes `<=3/20`
  - all six stability criteria must pass with artefact proof.

## Repo map
- `docs/architecture/`: canonical architecture + slice views (`diagram.control-plane.mmd`, `diagram.evidence-gates.mmd`, `diagram.learning-memory.mmd`).
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
- `memory_design_candidate`: `harness/skills/schemas/memory_design_candidate.schema.json`
- `edit_trace`: `harness/skills/schemas/edit_trace.schema.json`
- `routing_decision_packet`: `harness/skills/schemas/routing_decision_packet.schema.json`
- `debate_trace`: `harness/skills/schemas/debate_trace.schema.json`
- `harness_task_scorecard`: `harness/skills/schemas/harness_task_scorecard.schema.json`
- `harness_sufficiency_checkpoint`: `harness/skills/schemas/harness_sufficiency_checkpoint.schema.json`
- Output boundaries: `harness/skills/schemas/output_boundaries.schema.json`
- Merge authority policy: `harness/skills/schemas/merge_authority_policy.schema.json`
- Reward policy: `harness/skills/schemas/reward_policy.schema.json`
- Merge audit: `harness/skills/schemas/merge_authority_audit.schema.json`
- Opportunistic context resume: `harness/skills/schemas/opportunistic_resume_checkpoint.schema.json`

## Governance hard rules
- Subagents propose diffs only; only governor can merge after validator gates.
- Positive reward requires validator-improving progress and cost-bounded outcomes.
- Activity-volume rewards are forbidden (`skill_count_bonus` style terms fail policy checks).
- Opportunistic progress can resume from context memory via typed checkpoint contract.

## CI gate matrix
- `contracts-lint`: registry and schema lint.
- `contracts-validate-strict`: strict contract + fixture + fuzz validation.
- `policy-gates`: merge-authority and reward anti-gaming checks.
- `regression-pack`: known-good/known-bad stable reason-code checks.
- `json-render-smoke`: schema-authoritative JSON render smoke check with fail-closed invalid-input path.
- `checkpoint-contracts`: strict checkpoint schema and fixture enforcement.
- `checkpoint-regression-pack`: checkpoint-specific reason-code stability checks.
- `checkpoint-go-no-go-script`: deterministic dry-run validation for checkpoint computation.
- `docs-consistency`: docs must match strict governance semantics.
