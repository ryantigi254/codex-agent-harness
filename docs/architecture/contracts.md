# Contracts

Skill and gate I/O contracts are strict v2 JSON schemas under `harness/skills/schemas/`.

## Canonical contracts
- `SkillResult`: `skill_result.schema.json`
- `EvidenceObject`: `evidence_object.schema.json`
- `ValidatorResult`: `validator_result.schema.json`
- `ExperiencePacket`: `experience_packet.schema.json`

## Boundary and policy contracts
- `output_boundaries.schema.json`
  - `max_payload_bytes: 262144`
  - `max_array_items: 200`
  - `max_text_field_bytes: 65536`
  - `max_tool_calls: 200`
- `merge_authority_policy.schema.json`
  - subagents are proposal-only
  - governor review required for merge
  - validator gate required before merge
- `reward_policy.schema.json`
  - no activity-volume reward terms
  - positive progress requires validator improvement

## Contract enforcement
- Non-conforming payloads fail closed in strict validation.
- Pass/fail fixtures in `examples/contracts/` are part of CI and must stay deterministic.
