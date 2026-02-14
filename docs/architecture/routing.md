# Routing

Routing is entrypoint-driven via the skill picker, with explicit trigger metadata in the registry.

Control-plane view:
- `diagram.control-plane.mmd`

Hard requirements:
- every registry skill must include v2 `contract_ids` for `SkillResult`, `EvidenceObject`, `ValidatorResult`, and `ExperiencePacket`
- missing mapping fails CI at lint stage
