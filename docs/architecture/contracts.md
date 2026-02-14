# Contracts

Skill and gate I/O contracts are strict v2 JSON schemas under `harness/skills/schemas/`.

## Canonical contracts
- `SkillResult`: `skill_result.schema.json`
- `EvidenceObject`: `evidence_object.schema.json`
- `ValidatorResult`: `validator_result.schema.json`
- `ExperiencePacket`: `experience_packet.schema.json`

## Governance contracts
- `output_boundaries`: `output_boundaries.schema.json`
  - `max_payload_bytes: 262144`
  - `max_array_items: 200`
  - `max_text_field_bytes: 65536`
  - `max_tool_calls: 200`
- `merge_authority_policy`: `merge_authority_policy.schema.json`
- `reward_policy`: `reward_policy.schema.json`
- `merge_authority_audit`: `merge_authority_audit.schema.json`
- `opportunistic_resume_checkpoint`: `opportunistic_resume_checkpoint.schema.json`

## Deterministic fixtures
- pass fixtures: `examples/contracts/pass/`
- fail fixtures: `examples/contracts/fail/`
- deterministic fuzz fixtures: `examples/contracts/fuzz/`
- policy regression pack: `examples/contracts/regression/`

## Enforcement
- Non-conforming payloads fail closed in strict validation.
- `ValidatorResult` remains acceptance truth.
- `ExperiencePacket` remains learning input truth.
