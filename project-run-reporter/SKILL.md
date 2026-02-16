---
name: project-run-reporter
description: Generate high-standard, evidence-backed project run reports from repository state and persistent scratchpad notes. Use when a user asks for run reports, post-run summaries, implementation retrospectives, or correction logs that must include what changed, what failed, what was corrected, and validation evidence.
---

# Project Run Reporter

Produce concrete prior-run reports only.

## Enforced assumptions

- Treat every entry as a prior run; never label work as an active task.
- Use British English in prose.
- Keep reports concise and technically complete.
- Ground every claim in repository evidence or scratchpad evidence.

## Required evidence sources

Collect these every run:

1. Scratchpad at `../codex_scratchpad.md`.
2. `git status --short`.
3. `git log --oneline --decorate -n <N>` for the reporting window.
4. `git diff --name-only <range>` or scoped equivalent.
5. Test/lint output when relevant to changed behaviour.
6. Key changed files with concrete paths.
7. For recursive/context tasks: subcall trace and budget logs.

If any required evidence is missing, state `insufficient evidence` and identify exactly what is missing.

## Workflow

Execute in order:

1. Read scratchpad first; extract only actionable prior-run learning.
2. Collect repo evidence for the target window (commits, file diffs, validation outputs, failures).
3. Reconcile scratchpad claims against git/test evidence and flag mismatches explicitly.
4. Draft report using the exact structure in `references/report-template.md`.
5. Mark unsupported claims as `insufficient evidence`.
6. Return only the final report output (no process narration).

## Integrity rules

- Never invent actions, failures, test results, or file changes.
- Never claim completion without evidence (commit, diff, command output, or concrete file change).
- Never cite vague locations; always use concrete file paths.
- Never include secrets/tokens/credentials; replace with `redacted sensitive value`.
- Never include routine-progress scratchpad spam.

## Scratchpad update rule

Update `../codex_scratchpad.md` only when new learning exists:

- error or near-miss,
- correction,
- strategy switch,
- reusable rule or preference.

When updating, append one concise prior-run entry with:

- `Goal`
- `What changed`
- `Errors/near-misses` (if any)
- `Corrections`
- `What to do differently next time`
- `Follow-ups`

If no new learning occurred, skip scratchpad updates.

## Output contract

Always return both:

1. `Report summary` with 1-5 bullets.
2. Full report in one fenced Markdown block using `references/report-template.md`.

If user requests `full report`, output the complete report content, not only a summary.

For runs using `rlm-repl-runtime`, include:
- iteration count and whether `FINAL_VAR`-style termination was used,
- subcall count and peak subcalls per iteration,
- error rate (iterations with stderr),
- cost split (root vs subcalls, where logged),
- provenance coverage ratio (claims with source span / total claims),
- non-converged branches and disposition.

For multi-agent critique/debate runs, also emit:
- `reporting/<run_id>/debate_trace.json`

`debate_trace` minimum fields:
- `speaker_role`
- `timestamp`
- `claim_id`
- `counterclaim_id`
- `evidence_refs[]`

## Experience Packet Contract

Emit a machine-readable packet for downstream SkillBank flows:
- `reporting/<run_id>/experience_packet.json`
- `reporting/<run_id>/evaluation_log_packet.json`

Minimum packet fields:
- `run_id`
- `task_category`
- `outcome` (`success` or `failure`)
- `gate_failures`
- `action_summary`
- `key_evidence`
- `provenance_stats`
- `failure_objects` (if present)
- `memory_plugin`:
  - `id`
  - `version`
  - `retrieve_count`
  - `update_count`
- `guidance_overhead` (mandatory):
  - `guidance_chars`
  - `guidance_tokens_proxy`
  - `delta_vs_baseline`

Fail-closed rule:
- If `guidance_overhead` or `memory_plugin.id/version` are missing for memory-aware runs, mark report status as `failure` and emit `insufficient evidence`.

## Episode Telemetry Contract

Emit canonical RL-facing artefacts for every run:
- `reporting/<run_id>/episode_summary.json`
- `reporting/<run_id>/failure_packet_v2.json`

Episode summary minimum:
- `episode_summary`
- `final_reason_codes`
- `last_k_actions`
- `artifact_refs`

Failure packet minimum:
- `task_id`
- `run_id`
- `final_validators`
- `reason_codes`
- `last_k_actions`
- `tool_errors`
- `scratchpad_snapshot_ref`
- `diff_snapshot_ref`
- `missing_actions`

Command pattern:

```bash
python3 scripts/emit_episode_log.py --input /tmp/run_packet.json --output-dir reporting/<run_id>
```

```bash
python3 scripts/emit_debate_trace.py --input /tmp/debate_packet.json --output /tmp/debate_trace.json
```

Generate `guidance_overhead` using a deterministic helper script when raw counts are not already provided.

Command pattern:

```bash
python3 scripts/compute_guidance_overhead.py --experience-packet /tmp/experience_packet.json --baseline /tmp/baseline_packet.json --output /tmp/guidance_overhead.json
```

## Skill relationship wiring

- Runtime path: consume outputs from `rlm-repl-runtime`, `validation-gate-runner`, and `source-grounding-enforcer`.
- Visual communication path (optional): emit structured UI-ready JSON bundles consumable by `json-render`.
- Learning path: emit packets to `semantic-memory-compressor`, `memory-synthesiser`, and `experience-to-skill-distiller`.
- Evolution path: emit evaluation packets consumed by `regression-pattern-hunter`, `meta-memory-designer`, and `open-ended-memory-archive-manager`.

## Prompt-writing constraint

When asked to write a prompt for this workflow, include only task instructions, constraints, evidence requirements, and output requirements. Do not add persona-setting text.

## Standard SkillResult Telemetry

Every skill must emit a `SkillResult` envelope (or expose equivalent data for the harness adapter):
- `ok`
- `outputs`
- `tool_calls`
- `cost_units`
- `artefact_delta`
- `progress_proxy`
- `failure_codes`
- `suggested_next`

Compatibility phase:
- Legacy outputs are accepted when wrapped by the central harness adapter.

Strict phase:
- Missing or malformed `SkillResult` fails closed via `tool-contract-enforcer`.

Renderer guardrail:
- If UI rendering input is invalid against schema, emit `validation_failed/json_render_input_invalid`.
- Schema validation remains authoritative; renderer output is non-authoritative.
