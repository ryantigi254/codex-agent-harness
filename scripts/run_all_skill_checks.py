#!/usr/bin/env python3
"""Run full skill-system checks and emit performance report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOTS = [
    Path("/Users/ryangichuru/.codex/skills"),
    Path("/Users/ryangichuru/.cursor/skills"),
    Path("/Users/ryangichuru/Downloads/skills"),
]

CODEX_ROOT = Path("/Users/ryangichuru/.codex/skills")
SCRATCHPAD_VALIDATOR = CODEX_ROOT / "scratchpad-governor/scripts/verify_scratchpad_update.py"
SKILLBANK_VALIDATE = CODEX_ROOT / "skillbank-store-versioning/scripts/validate_skillbank_schema.py"
SKILLBANK_UPSERT = CODEX_ROOT / "skillbank-store-versioning/scripts/upsert_skillbank_entry.py"
RETRIEVE = CODEX_ROOT / "adaptive-skill-retriever/scripts/select_guidance.py"
BUNDLE = CODEX_ROOT / "adaptive-skill-retriever/scripts/build_guidance_bundle.py"
FULL_FLOW = CODEX_ROOT / "rlm-repl-runtime/scripts/run_full_research_flow.py"
FANOUT_BENCH = CODEX_ROOT / "rlm-repl-runtime/scripts/run_fanout_benchmark.py"
RUNTIME_SUITE = CODEX_ROOT / "rlm-repl-runtime/scripts/run_local_test_suite.py"
STRATEGY_RUN_VALIDATOR = CODEX_ROOT / "scripts/validate_strategy_run.py"
STRATEGY_AGGREGATOR = CODEX_ROOT / "scripts/run_strategy_matrix.py"
STRATEGY_REBUILDER = CODEX_ROOT / "scripts/rebuild_strategy_telemetry.py"
VALIDATE_SKILL_RESULT = CODEX_ROOT / "scripts/validate_skill_result.py"
COMPUTE_CENTRAL_REWARD = CODEX_ROOT / "scripts/compute_central_reward.py"
SKILL_RESULT_SCHEMA = CODEX_ROOT / "scripts/skill_result_schema.json"
REWARD_CONTRACT_SCHEMA = CODEX_ROOT / "scripts/reward_contract_schema.json"
FAILURE_PACKET_SCHEMA = CODEX_ROOT / "scripts/failure_packet_schema.json"
CHECKLIST_CONTRACT_SCHEMA = CODEX_ROOT / "scripts/checklist_contract_schema.json"
SNAPSHOT_INDEX_SCHEMA = CODEX_ROOT / "scripts/snapshot_index_schema.json"
CONTEXT_REPO_CONTRACT_SCHEMA = CODEX_ROOT / "scripts/context_repo_contract_schema.json"
MEMORY_FRONTMATTER_SCHEMA = CODEX_ROOT / "scripts/memory_file_frontmatter_schema.json"
MEMORY_UPDATE_BUNDLE_SCHEMA = CODEX_ROOT / "scripts/memory_update_bundle_schema.json"
EVIDENCE_OBJECT_SCHEMA = CODEX_ROOT / "scripts/evidence_object_schema.json"
OUTPUT_BOUNDARY_LIMITS = CODEX_ROOT / "scripts/output_boundary_limits.json"
EXECUTION_AUDIT_CONTRACT_SCHEMA = CODEX_ROOT / "scripts/execution_audit_contract_schema.json"
LETTA_POINTER_CONTRACT_SCHEMA = CODEX_ROOT / "scripts/letta_pointer_contract_schema.json"
REASON_TAXONOMY = CODEX_ROOT / "scripts/reason_code_taxonomy.json"
STRICT_MODE_STATE_PATH = CODEX_ROOT / "scripts/strict_mode_transition.json"
EMIT_FAILURE_LESSONS = CODEX_ROOT / "rlm-repl-runtime/scripts/emit_failure_lesson_candidates.py"
GUIDANCE_OVERHEAD = CODEX_ROOT / "project-run-reporter/scripts/compute_guidance_overhead.py"
CANDIDATE_DELTAS = CODEX_ROOT / "regression-pattern-hunter/scripts/build_candidate_skill_deltas.py"
MEMORY_INTERFACE = CODEX_ROOT / "memory-design-interface/scripts/run_memory_design_interface.py"
SANDBOX_PROFILE = CODEX_ROOT / "sandbox-profile-manager/scripts/run_sandbox_profile_manager.py"
COMPUTE_PROGRESS_PROXY = CODEX_ROOT / "long-run-stability-guard/scripts/compute_progress_proxy.py"
BUILD_SNAPSHOT_INDEX = CODEX_ROOT / "playwright-browser-screenshot-workflow/scripts/build_snapshot_index.py"
VALIDATE_SNAPSHOT_GROUNDING = CODEX_ROOT / "source-grounding-enforcer/scripts/validate_snapshot_grounding.py"
WRITE_MEMORY_REPO_ENTRY = CODEX_ROOT / "scratchpad-governor/scripts/write_memory_repo_entry.py"
MIGRATE_STABLE_PATTERNS = CODEX_ROOT / "scratchpad-governor/scripts/migrate_stable_patterns_to_memory_repo.py"
DEFRAG_MEMORY_REPO = CODEX_ROOT / "scratchpad-governor/scripts/defrag_memory_repo.py"
CREATE_MEMORY_WORKTREES = CODEX_ROOT / "subagent-dag-orchestrator/scripts/create_memory_worktrees.py"
MERGE_MEMORY_WORKTREE_CANDIDATES = CODEX_ROOT / "subagent-dag-orchestrator/scripts/merge_memory_worktree_candidates.py"
EMIT_EXPERIENCE_PACKET = CODEX_ROOT / "project-run-reporter/scripts/emit_experience_packet.py"
DISTILLER_SCRIPT = CODEX_ROOT / "experience-to-skill-distiller/scripts/run_experience_to_skill_distiller.py"
DISTILLER_PROPOSAL_SCHEMA = CODEX_ROOT / "experience-to-skill-distiller/references/proposal_bundle_schema.json"
EMIT_EDIT_TRACE = CODEX_ROOT / "self-correction-loop/scripts/emit_edit_trace.py"
EMIT_ROUTING_DECISION_PACKET = CODEX_ROOT / "uncertainty-calibrated-answering/scripts/emit_routing_decision_packet.py"
EMIT_MEMORY_DESIGN_CANDIDATE = CODEX_ROOT / "experience-to-skill-distiller/scripts/emit_memory_design_candidate.py"
EMIT_DEBATE_TRACE = CODEX_ROOT / "project-run-reporter/scripts/emit_debate_trace.py"
JSON_RENDER_SMOKE = CODEX_ROOT / "codex-agent-harness/scripts/json_render_smoke.py"
HARNESS_PASS_ROUTING_FIXTURE = CODEX_ROOT / "codex-agent-harness/examples/contracts/pass/routing_decision_packet.json"
HARNESS_FAIL_ROUTING_FIXTURE = CODEX_ROOT / "codex-agent-harness/examples/contracts/fail/routing_decision_packet_chosen_model_missing_from_candidates.json"
RUN_UNTIL_GREEN = CODEX_ROOT / "validation-gate-runner/scripts/run_until_green.py"
CTX_ADAPTER = CODEX_ROOT / "rlm-repl-runtime/scripts/context_adapter.py"
CTX_NAV = CODEX_ROOT / "rlm-repl-runtime/scripts/build_navigation_plan.py"
GENERATE_SKILL_DOCS = CODEX_ROOT / "scripts/generate_skill_docs.py"
VALIDATE_SKILL_DOCS = CODEX_ROOT / "scripts/validate_skill_docs.py"
LETTA_ADAPTER = CODEX_ROOT / "scripts/letta_adapter.py"
SECRET_SCAN = CODEX_ROOT / "scripts/scan_secrets.py"
STAGE_LETTA_DRAFT = CODEX_ROOT / "scratchpad-governor/scripts/stage_letta_draft.py"
PUBLISH_LETTA_DRAFTS = CODEX_ROOT / "scratchpad-governor/scripts/publish_letta_drafts.py"
DOCS_ROOT = CODEX_ROOT / "docs"
SKILLBANK_FIXTURES = CODEX_ROOT / "rlm-repl-runtime/tests/fixtures/skillbank"
STRING_FIXTURE = CODEX_ROOT / "rlm-repl-runtime/tests/fixtures/string_smoke"
LITREVIEW_FIXTURE = CODEX_ROOT / "rlm-repl-runtime/tests/fixtures/full_scale_litreview"


def run_cmd(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.time()
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
    )
    elapsed = round((time.time() - started) * 1000.0, 2)
    return {
        "command": command,
        "exit_code": result.returncode,
        "duration_ms": elapsed,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "ok": result.returncode == 0,
    }


def audit_parity() -> dict[str, Any]:
    details = []
    overall_ok = True
    for root in ROOTS:
        if not root.exists():
            details.append(
                {
                    "root": str(root),
                    "ok": True,
                    "missing_agents": [],
                    "missing_scripts": [],
                    "note": "root_missing_skipped",
                }
            )
            continue
        missing_agents = []
        missing_scripts = []
        for skill in sorted([p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").exists()]):
            if not (skill / "agents/openai.yaml").exists():
                missing_agents.append(skill.name)
            if not (skill / "scripts").exists():
                missing_scripts.append(skill.name)
        root_ok = not missing_agents
        overall_ok = overall_ok and root_ok
        details.append(
            {
                "root": str(root),
                "ok": root_ok,
                "missing_agents": missing_agents,
                "missing_scripts": missing_scripts,
            }
        )
    return {"name": "parity_audit", "ok": overall_ok, "details": details}


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sync_and_verify_three_roots() -> dict[str, Any]:
    source = CODEX_ROOT
    targets = [Path("/Users/ryangichuru/.cursor/skills"), Path("/Users/ryangichuru/Downloads/skills")]
    synced = 0
    skipped_dirs = {"__pycache__", ".git"}
    source_files = [p for p in source.rglob("*") if p.is_file() and not any(part in skipped_dirs for part in p.parts)]
    for src_file in source_files:
        rel = src_file.relative_to(source)
        for target_root in targets:
            dst = target_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)
            synced += 1

    mismatches: list[dict[str, str]] = []
    for src_file in source_files:
        rel = src_file.relative_to(source)
        src_hash = sha256_file(src_file)
        for target_root in targets:
            dst = target_root / rel
            if not dst.exists():
                mismatches.append({"file": str(rel), "target": str(target_root), "reason": "missing"})
                continue
            dst_hash = sha256_file(dst)
            if src_hash != dst_hash:
                mismatches.append({"file": str(rel), "target": str(target_root), "reason": "sha_mismatch"})
    return {
        "name": "sync_and_sha_verify",
        "ok": not mismatches,
        "synced_copies": synced,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
    }


def skip_sync_notice() -> dict[str, Any]:
    return {
        "name": "sync_and_sha_verify",
        "ok": True,
        "details": [{"note": "mirror sync skipped (codex root only scope)"}],
    }


def write_temp_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required_fields(payload: dict[str, Any], required_fields: list[str]) -> list[str]:
    return [field for field in required_fields if field not in payload]


def run_typed_validator_checks(tmp_dir: Path) -> dict[str, Any]:
    task = tmp_dir / "task.json"
    exp = tmp_dir / "experience.json"
    failure = tmp_dir / "failure.json"
    skill_entry = tmp_dir / "skillbank.json"
    bad = tmp_dir / "bad.json"

    write_temp_json(
        task,
        {
            "task_signature": "lit-review",
            "impact": 80,
            "urgency": 70,
            "recurrence": 60,
            "blocker_risk": 75,
            "confidence": 0.8,
            "source_refs": ["logs/run1.json"],
            "status": "active",
            "next_actions": ["rerun extraction"],
        },
    )
    write_temp_json(
        exp,
        {
            "entry_type": "experience_packet",
            "run_id": "run-01",
            "task_signature": "lit-review",
            "task_category": "research",
            "executor_mode": "repl",
            "skill_stack_used": ["skill-picker-orchestrator", "rlm-repl-runtime"],
            "guidance_pack_used": ["gen-001"],
            "outcome": "success",
            "gate_failures": [],
            "evidence_refs": ["/tmp/rlm/run-01/summary.json"],
            "cost_proxy": {"iterations": 3},
        },
    )
    write_temp_json(
        failure,
        {
            "entry_type": "failure_packet",
            "failure_mode": "grounding_missing",
            "symptom": "Two claims lacked provenance",
            "suspected_root_cause": "Skipped verify step",
            "mitigation_candidate": "Force claim-span check",
            "minimal_repro_refs": ["/tmp/rlm/run-02/trajectory.jsonl"],
            "severity": "high",
            "recurrence_count": 2,
            "reason_codes": ["missing_sources"],
            "missing_actions": ["use_source_grounding"],
        },
    )
    write_temp_json(
        skill_entry,
        {
            "entry_type": "skillbank_entry",
            "skill_id": "kb-001",
            "title": "Ground claims first",
            "principle": "Map claims to spans before synthesis",
            "when_to_apply": "Research synthesis tasks",
            "hierarchy": "task_specific",
            "task_category": "research",
            "source_refs": ["/tmp/reporting/experience_packet.json"],
            "version": 1,
            "status": "draft",
        },
    )
    write_temp_json(bad, {"entry_type": "unknown_type"})

    checks = [
        run_cmd([sys.executable, str(SCRATCHPAD_VALIDATOR), "--entry-json", str(task)]),
        run_cmd([sys.executable, str(SCRATCHPAD_VALIDATOR), "--entry-json", str(exp)]),
        run_cmd([sys.executable, str(SCRATCHPAD_VALIDATOR), "--entry-json", str(failure)]),
        run_cmd([sys.executable, str(SCRATCHPAD_VALIDATOR), "--entry-json", str(skill_entry)]),
    ]
    bad_check = run_cmd([sys.executable, str(SCRATCHPAD_VALIDATOR), "--entry-json", str(bad)])
    checks.append({**bad_check, "expected_failure": True, "ok": bad_check["exit_code"] != 0})

    return {
        "name": "typed_validator_checks",
        "ok": all(item["ok"] for item in checks),
        "details": checks,
    }


def run_failure_packet_strictness_checks(tmp_dir: Path) -> dict[str, Any]:
    bad_failure = tmp_dir / "failure_bad.json"
    good_failure = tmp_dir / "failure_good.json"

    write_temp_json(
        bad_failure,
        {
            "entry_type": "failure_packet",
            "failure_mode": "grounding_missing",
            "symptom": "Two claims lacked provenance",
            "suspected_root_cause": "Skipped verify step",
            "mitigation_candidate": "Force claim-span check",
            "minimal_repro_refs": ["/tmp/rlm/run-02/trajectory.jsonl"],
            "severity": "high",
            "recurrence_count": 2,
        },
    )
    write_temp_json(
        good_failure,
        {
            "entry_type": "failure_packet",
            "failure_mode": "grounding_missing",
            "symptom": "Two claims lacked provenance",
            "suspected_root_cause": "Skipped verify step",
            "mitigation_candidate": "Force claim-span check",
            "minimal_repro_refs": ["/tmp/rlm/run-02/trajectory.jsonl"],
            "severity": "high",
            "recurrence_count": 2,
            "reason_codes": ["missing_sources"],
            "missing_actions": ["use_source_grounding"],
        },
    )

    compat_bad = run_cmd(
        [
            sys.executable,
            str(SCRATCHPAD_VALIDATOR),
            "--entry-json",
            str(bad_failure),
            "--failure-packet-mode",
            "compat",
        ]
    )
    strict_bad = run_cmd(
        [
            sys.executable,
            str(SCRATCHPAD_VALIDATOR),
            "--entry-json",
            str(bad_failure),
            "--failure-packet-mode",
            "strict",
        ]
    )
    strict_good = run_cmd(
        [
            sys.executable,
            str(SCRATCHPAD_VALIDATOR),
            "--entry-json",
            str(good_failure),
            "--failure-packet-mode",
            "strict",
        ]
    )
    ok = compat_bad["ok"] and (strict_bad["exit_code"] != 0) and strict_good["ok"]
    return {
        "name": "failure_packet_strictness_checks",
        "ok": ok,
        "details": [
            {**compat_bad, "expected": "pass_in_compat"},
            {**strict_bad, "expected_failure": True, "expected": "fail_in_strict"},
            {**strict_good, "expected": "pass_in_strict"},
        ],
    }


def run_skillbank_flow(tmp_dir: Path) -> dict[str, Any]:
    valid_entry = tmp_dir / "entry.json"
    write_temp_json(
        valid_entry,
        {
            "skill_id": "smoke-001",
            "title": "Ground claims before synthesis",
            "principle": "Always map claims to evidence spans",
            "when_to_apply": "Literature review synthesis",
            "hierarchy": "task_specific",
            "task_category": "literature_review",
            "version": 1,
            "source_runs": ["smoke-run"],
        },
    )
    retrieval_json = tmp_dir / "retrieval.json"

    steps = []
    steps.append(run_cmd([sys.executable, str(SKILLBANK_VALIDATE), "--input-json", str(valid_entry)]))
    steps.append(
        run_cmd(
            [
                sys.executable,
                str(SKILLBANK_UPSERT),
                "--entry-json",
                str(valid_entry),
                "--skillbank-root",
                str(tmp_dir / "skillbank"),
                "--reason",
                "umbrella smoke",
            ]
        )
    )
    retrieve = run_cmd(
        [
            sys.executable,
            str(RETRIEVE),
            "--skillbank-index",
            str(SKILLBANK_FIXTURES / "index.json"),
            "--task-description",
            "clinical literature review with evidence mapping",
            "--experience-packet",
            str(SKILLBANK_FIXTURES / "experience_packet.json"),
            "--threshold",
            "0.05",
            "--top-k",
            "2",
        ]
    )
    steps.append(retrieve)
    if retrieve["ok"]:
        retrieval_json.write_text(retrieve["stdout"], encoding="utf-8")
        steps.append(
            run_cmd(
                [
                    sys.executable,
                    str(BUNDLE),
                    "--retrieval-json",
                    str(retrieval_json),
                    "--experience-packet",
                    str(SKILLBANK_FIXTURES / "experience_packet.json"),
                    "--current-progress",
                    "phase: synthesis",
                    "--current-observation",
                    "two claims unresolved",
                ]
            )
        )

    return {"name": "skillbank_flow", "ok": all(item["ok"] for item in steps), "details": steps}


def run_full_research_flow(tmp_dir: Path) -> dict[str, Any]:
    result = run_cmd(
        [
            sys.executable,
            str(FULL_FLOW),
            "--input-root",
            str(STRING_FIXTURE),
            "--run-id",
            "umbrella-flow",
            "--output-dir",
            str(tmp_dir / "flow"),
            "--query",
            "extract key facts",
            "--final-answer",
            '{"status":"ok"}',
        ]
    )
    return {"name": "full_research_flow", "ok": result["ok"], "details": [result]}


def run_fanout_benchmark(_tmp_dir: Path) -> dict[str, Any]:
    run_id = f"umbrella-fanout-{int(time.time())}"
    result = run_cmd(
        [
            sys.executable,
            str(FANOUT_BENCH),
            "--input-root",
            str(LITREVIEW_FIXTURE),
            "--run-id",
            run_id,
            "--output-root",
            "/tmp",
            "--mode",
            "sweep",
        ]
    )
    parsed = {}
    if result["ok"] and result["stdout"]:
        try:
            parsed = json.loads(result["stdout"])
        except json.JSONDecodeError:
            parsed = {}
    output_dir = Path(parsed.get("output_dir", ""))
    artefacts_ok = bool(parsed.get("ok")) and output_dir.exists()
    required = [
        output_dir / "fanout_summary.json",
        output_dir / "fanout_events.jsonl",
        output_dir / "merge_quality.json",
        output_dir / "gate_degradation.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    ok = result["ok"] and artefacts_ok and not missing
    return {
        "name": "fanout_benchmark",
        "ok": ok,
        "details": [result],
        "metrics": parsed.get("aggregate", {}),
        "artefacts": {k: parsed.get(k, "") for k in ["fanout_summary", "fanout_events", "merge_quality", "gate_degradation"]},
        "missing_artefacts": missing,
        "output_dir": parsed.get("output_dir", ""),
    }


def run_runtime_suite() -> dict[str, Any]:
    result = run_cmd([sys.executable, str(RUNTIME_SUITE)])
    parsed = {}
    if result["ok"] and result["stdout"]:
        lines = [line for line in result["stdout"].splitlines() if line.strip()]
        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError:
            parsed = {}
    return {
        "name": "runtime_suite",
        "ok": result["ok"] and parsed.get("status") == "ok",
        "details": [result],
        "metrics": parsed.get("metrics", {}),
        "suite_status": parsed.get("status"),
        "missing_artefacts": parsed.get("missing_artefacts", []),
    }


def run_strategy_comparison_snapshot(strategy_dir: Path, rebuild_telemetry: bool = False) -> dict[str, Any]:
    out_json = strategy_dir / "strategy_comparison.json"
    out_md = strategy_dir / "strategy_comparison_table.md"
    if not strategy_dir.exists():
        return {
            "name": "strategy_comparison_snapshot",
            "ok": True,
            "details": [{"note": "strategy dir not present; skipped"}],
        }
    run_files = sorted(strategy_dir.glob("run_*.json"))
    if not run_files:
        return {
            "name": "strategy_comparison_snapshot",
            "ok": True,
            "details": [{"note": "no strategy run files; skipped"}],
        }
    details: list[dict[str, Any]] = []
    if rebuild_telemetry:
        rebuild_step = run_cmd([sys.executable, str(STRATEGY_REBUILDER), "--runs-dir", str(strategy_dir)])
        details.append(rebuild_step)
        if not rebuild_step["ok"]:
            return {
                "name": "strategy_comparison_snapshot",
                "ok": False,
                "details": details,
                "invalid_files": ["telemetry rebuild failed"],
            }
    validate_steps = [
        run_cmd([sys.executable, str(STRATEGY_RUN_VALIDATOR), "--run-json", str(path), "--schema-json", str(CODEX_ROOT / "scripts/strategy_run_schema.json")])
        for path in run_files
    ]
    invalid_files: list[str] = []
    invalid_details: list[dict[str, Any]] = []
    for step in validate_steps:
        if step["ok"]:
            continue
        parsed = {}
        try:
            parsed = json.loads(step.get("stdout", "") or "{}")
        except json.JSONDecodeError:
            parsed = {}
        run_path = parsed.get("run_path", "unknown")
        invalid_files.append(run_path)
        invalid_details.append(
            {
                "run_path": run_path,
                "errors": parsed.get("errors", ["validator returned non-zero exit code"]),
                "validator_exit_code": step["exit_code"],
            }
        )
    if invalid_files:
        return {
            "name": "strategy_comparison_snapshot",
            "ok": False,
            "details": details + invalid_details,
            "invalid_files": invalid_files,
        }
    aggregate = run_cmd(
        [
            sys.executable,
            str(STRATEGY_AGGREGATOR),
            "--runs-dir",
            str(strategy_dir),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    return {
        "name": "strategy_comparison_snapshot",
        "ok": aggregate["ok"] and out_json.exists() and out_md.exists(),
        "details": details + validate_steps + [aggregate],
        "artefacts": {"strategy_comparison_json": str(out_json), "strategy_comparison_md": str(out_md)},
    }


def run_memory_contract_smoke(tmp_dir: Path) -> dict[str, Any]:
    experience = tmp_dir / "exp.json"
    baseline = tmp_dir / "baseline.json"
    failure_clusters = tmp_dir / "clusters.json"
    output_overhead = tmp_dir / "overhead.json"
    output_deltas = tmp_dir / "deltas.json"
    run_root = tmp_dir / "rlm" / "run-001"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "trajectory.jsonl").write_text(json.dumps({"iteration": 1}) + "\n", encoding="utf-8")
    failure_objects = tmp_dir / "failure_objects.json"
    output_lessons = tmp_dir / "failure_lesson_candidates.jsonl"
    memory_interface_in = tmp_dir / "memory_interface.json"
    memory_interface_out = tmp_dir / "memory_interface_out.json"
    sandbox_good_in = tmp_dir / "sandbox_good.json"
    sandbox_bad_in = tmp_dir / "sandbox_bad.json"
    sandbox_good_out = tmp_dir / "sandbox_good_out.json"
    sandbox_bad_out = tmp_dir / "sandbox_bad_out.json"
    eval_packet = tmp_dir / "evaluation_packet.json"

    write_temp_json(experience, {"guidance_pack_used": ["gen:verify", "task:clinical-table"]})
    write_temp_json(baseline, {"guidance_pack_used": ["gen:verify"]})
    write_temp_json(
        eval_packet,
        {
            "run_id": "run-001",
            "memory_plugin": {"id": "mem-basic", "version": "1.0.0", "retrieve_count": 2, "update_count": 1},
        },
    )
    write_temp_json(
        failure_clusters,
        {
            "failure_clusters": [
                {
                    "failure_description": "grounding missing for two claims",
                    "mitigation_candidate": "force claim-to-span mapping",
                    "confidence": 0.72,
                    "evidence_refs": ["/tmp/run/trajectory.jsonl"],
                }
            ]
        },
    )
    write_temp_json(
        failure_objects,
        [
            {
                "id": "failure-1",
                "iteration": 1,
                "failure_description": "grounding missing",
                "root_cause_candidate": "no span extraction",
                "mitigation_hint": "extract direct span before summary",
                "minimal_repro_refs": ["/tmp/run/trajectory.jsonl"],
            }
        ],
    )
    write_temp_json(
        memory_interface_in,
        {
            "memory_plugin": {"id": "mem-basic", "version": "1.0.0"},
            "operations": {
                "retrieve": {"input_schema": {"query": "string"}, "output_schema": {"units": "array"}},
                "update": {"input_schema": {"packet": "object"}, "output_schema": {"ack": "boolean"}},
            },
        },
    )
    write_temp_json(
        sandbox_good_in,
        {
            "run_id": "memory-contract-smoke",
            "trust_level": "generated_untrusted",
            "requested_profile": "docker",
            "audit_ref": "/tmp/audit/memory-contract-smoke.json",
        },
    )
    write_temp_json(
        sandbox_bad_in,
        {
            "run_id": "memory-contract-smoke",
            "trust_level": "generated_untrusted",
            "requested_profile": "local",
            "audit_ref": "",
        },
    )

    steps = [
        run_cmd(
            [
                sys.executable,
                str(GUIDANCE_OVERHEAD),
                "--experience-packet",
                str(experience),
                "--baseline",
                str(baseline),
                "--output",
                str(output_overhead),
            ]
        ),
        run_cmd(
            [
                sys.executable,
                str(CANDIDATE_DELTAS),
                "--failure-clusters",
                str(failure_clusters),
                "--output",
                str(output_deltas),
            ]
        ),
        run_cmd(
            [
                sys.executable,
                str(EMIT_FAILURE_LESSONS),
                "--run-root",
                str(run_root),
                "--failure-objects",
                str(failure_objects),
                "--output",
                str(output_lessons),
            ]
        ),
        run_cmd([sys.executable, str(MEMORY_INTERFACE), "--input", str(memory_interface_in), "--output", str(memory_interface_out)]),
        run_cmd([sys.executable, str(SANDBOX_PROFILE), "--input", str(sandbox_good_in), "--output", str(sandbox_good_out)]),
    ]
    bad_sandbox = run_cmd([sys.executable, str(SANDBOX_PROFILE), "--input", str(sandbox_bad_in), "--output", str(sandbox_bad_out)])
    steps.append({**bad_sandbox, "expected_failure": True, "ok": bad_sandbox["exit_code"] != 0})
    artefacts = [output_overhead, output_deltas, output_lessons]
    missing = [str(path) for path in artefacts if not path.exists()]
    semantic_ok = True
    semantic_errors: list[str] = []
    try:
        overhead_payload = read_json(output_overhead)
        for key in ("guidance_chars", "guidance_tokens_proxy", "delta_vs_baseline"):
            if key not in overhead_payload:
                semantic_ok = False
                semantic_errors.append(f"missing overhead field: {key}")
        delta_payload = read_json(output_deltas)
        if not isinstance(delta_payload.get("candidate_skill_deltas"), list) or not delta_payload["candidate_skill_deltas"]:
            semantic_ok = False
            semantic_errors.append("candidate_skill_deltas missing/empty")
        else:
            sample_delta = delta_payload["candidate_skill_deltas"][0]
            for key in ("skill_id", "principle", "when_to_apply", "confidence", "evidence_refs"):
                if key not in sample_delta:
                    semantic_ok = False
                    semantic_errors.append(f"missing delta field: {key}")
        eval_payload = read_json(eval_packet)
        plugin = eval_payload.get("memory_plugin", {})
        if not isinstance(plugin, dict) or not plugin.get("id") or not plugin.get("version"):
            semantic_ok = False
            semantic_errors.append("missing memory_plugin.id/version")
    except json.JSONDecodeError:
        semantic_ok = False
        semantic_errors.append("failed to parse generated smoke artefacts")
    return {
        "name": "memory_contract_smoke",
        "ok": all(step["ok"] for step in steps) and not missing and semantic_ok,
        "details": steps,
        "missing_artefacts": missing,
        "semantic_errors": semantic_errors,
    }


def run_skillresult_and_reward_checks(tmp_dir: Path, strict_skill_result: bool = False) -> dict[str, Any]:
    sample_skill_result = tmp_dir / "skill_result.json"
    sample_reward_input = tmp_dir / "reward_input.json"
    sample_reward_output = tmp_dir / "reward_output.json"
    sample_failure = tmp_dir / "failure_packet.json"
    tool_contract_input = tmp_dir / "tool_contract_input.json"

    write_temp_json(
        sample_skill_result,
        {
            "ok": True,
            "outputs": {"summary": "smoke"},
            "tool_calls": [{"tool_name": "smoke", "params_hash": "abc123", "duration_ms": 1.2}],
            "cost_units": {"time_ms": 1.2, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
            "artefact_delta": {"files_changed": [], "tests_run": [], "urls_fetched": []},
            "progress_proxy": {"delta": 0.1},
            "failure_codes": [],
            "suggested_next": [],
        },
    )
    write_temp_json(
        sample_reward_input,
        {
            "run_id": "smoke-run",
            "skill_result": read_json(sample_skill_result),
            "validator_state": {
                "all_passed": True,
                "improved": True,
                "progress_delta": 0.3,
                "reason_codes": [],
            },
            "budget_state": {"remaining_steps": 4, "remaining_time_ms": 5000, "repeated_actions_count": 0},
            "success": True,
            "progress_delta": 0.3,
            "cost": 1.0,
            "invalid": False,
            "no_progress": False,
            "spam": 0.0,
            "reason_codes": [],
        },
    )
    write_temp_json(
        sample_failure,
        {
            "task_id": "smoke-task",
            "run_id": "smoke-run",
            "final_validators": {"tests": False},
            "reason_codes": ["tests_not_run"],
            "last_k_actions": [{"skill_id": "validation-gate-runner"}],
            "tool_errors": [],
            "scratchpad_snapshot_ref": "/tmp/scratchpad.md",
            "diff_snapshot_ref": "/tmp/diff.patch",
            "missing_actions": ["run_validation_tests"],
        },
    )
    write_temp_json(
        tool_contract_input,
        {
            "validate_skill_result": True,
            "required_fields": [],
            "required_types": {},
            "payload": read_json(sample_skill_result),
        },
    )

    steps = [
        run_cmd([sys.executable, str(VALIDATE_SKILL_RESULT), "--input", str(sample_skill_result)] + (["--strict"] if strict_skill_result else [])),
        run_cmd([sys.executable, str(COMPUTE_CENTRAL_REWARD), "--input", str(sample_reward_input), "--output", str(sample_reward_output)]),
        run_cmd([sys.executable, str(CODEX_ROOT / "scripts/test_skillresult_validation.py")]),
        run_cmd([sys.executable, str(CODEX_ROOT / "scripts/test_central_reward.py")]),
        run_cmd(
            [
                sys.executable,
                str(CODEX_ROOT / "tool-contract-enforcer/scripts/run_tool_contract_enforcer.py"),
                "--input",
                str(tool_contract_input),
                "--output",
                str(tmp_dir / "tool_contract_output.json"),
            ]
            + (["--strict-skill-result"] if strict_skill_result else [])
        ),
    ]

    schema_errors: list[str] = []
    try:
        skill_schema = read_json(SKILL_RESULT_SCHEMA)
        reward_schema = read_json(REWARD_CONTRACT_SCHEMA)
        failure_schema = read_json(FAILURE_PACKET_SCHEMA)
        checklist_schema = read_json(CHECKLIST_CONTRACT_SCHEMA)
        skill_payload = read_json(sample_skill_result)
        reward_payload = read_json(sample_reward_output)
        failure_payload = read_json(sample_failure)
        checklist_payload = {
            "run_id": "smoke-run",
            "items": [],
            "termination_policy": "strict_gate",
            "reason_codes": [],
            "version": "1.0.0",
        }

        schema_errors.extend([f"skill_result.{f}" for f in validate_required_fields(skill_payload, skill_schema.get("required", []))])
        schema_errors.extend([f"reward.{f}" for f in validate_required_fields(reward_payload, reward_schema.get("required", []))])
        schema_errors.extend([f"failure_packet.{f}" for f in validate_required_fields(failure_payload, failure_schema.get("required", []))])
        schema_errors.extend([f"checklist_contract.{f}" for f in validate_required_fields(checklist_payload, checklist_schema.get("required", []))])
    except json.JSONDecodeError:
        schema_errors.append("schema_parse_error")

    return {
        "name": "skillresult_and_reward_checks",
        "ok": all(step["ok"] for step in steps) and not schema_errors,
        "details": steps,
        "schema_errors": schema_errors,
        "strict_skill_result": strict_skill_result,
    }


def run_checklist_contract_checks(tmp_dir: Path) -> dict[str, Any]:
    task_path = tmp_dir / "checklist_task.json"
    output_dir = tmp_dir / "checklist_contract"
    cycle_task_path = tmp_dir / "checklist_cycle_task.json"
    contract_input = tmp_dir / "checklist_contract_enforcer.json"
    contract_output = tmp_dir / "checklist_contract_enforcer_out.json"

    write_temp_json(
        task_path,
        {
            "acceptance_tests": [{"name": "echo_ok", "command": "python3 -c 'print(\"ok\")'"}],
            "checklist_contract": {
                "items": [
                    {
                        "item_id": "item-1",
                        "question": "Did validation pass?",
                        "evidence_required": ["iteration_log"],
                        "strictness": "strict",
                        "depends_on": [],
                        "status": "unsatisfied",
                        "satisfied_at_step": None,
                        "evidence_refs": [],
                        "pass_when_check": "echo_ok",
                    }
                ]
            },
        },
    )
    write_temp_json(
        cycle_task_path,
        {
            "acceptance_tests": [{"name": "echo_ok", "command": "python3 -c 'print(\"ok\")'"}],
            "checklist_contract": {
                "items": [
                    {
                        "item_id": "a",
                        "question": "A",
                        "evidence_required": ["x"],
                        "strictness": "normal",
                        "depends_on": ["b"],
                        "status": "unsatisfied",
                        "satisfied_at_step": None,
                        "evidence_refs": [],
                    },
                    {
                        "item_id": "b",
                        "question": "B",
                        "evidence_required": ["x"],
                        "strictness": "normal",
                        "depends_on": ["a"],
                        "status": "unsatisfied",
                        "satisfied_at_step": None,
                        "evidence_refs": [],
                    },
                ]
            },
        },
    )

    compile_ok = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "validation-gate-runner/scripts/compile_checks.py"),
            "--task-json",
            str(task_path),
            "--run-id",
            "checklist-ok",
            "--output-dir",
            str(output_dir),
        ]
    )
    cycle_fail = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "validation-gate-runner/scripts/compile_checks.py"),
            "--task-json",
            str(cycle_task_path),
            "--run-id",
            "checklist-cycle",
            "--output-dir",
            str(tmp_dir / "checklist_cycle"),
        ]
    )

    errors: list[str] = []
    if compile_ok["ok"]:
        contract = read_json(output_dir / "contract.json")
        write_temp_json(
            contract_input,
            {
                "validate_checklist_contract": True,
                "checklist_payload": contract.get("checklist_contract", {}),
                "payload": {},
            },
        )
        enforce = run_cmd(
            [
                sys.executable,
                str(CODEX_ROOT / "tool-contract-enforcer/scripts/run_tool_contract_enforcer.py"),
                "--input",
                str(contract_input),
                "--output",
                str(contract_output),
                "--strict-checklist",
            ]
        )
    else:
        enforce = {"ok": False, "exit_code": 1, "stdout": "", "stderr": "compile failed"}
        errors.append("compile_ok_failed")

    if cycle_fail["exit_code"] == 0:
        errors.append("cycle_task_should_fail_closed")
    if not enforce.get("ok", False):
        errors.append("checklist_contract_enforcer_failed")

    return {
        "name": "checklist_contract_checks",
        "ok": compile_ok["ok"] and cycle_fail["exit_code"] != 0 and enforce.get("ok", False) and not errors,
        "details": [compile_ok, {**cycle_fail, "expected_failure": True}, enforce],
        "errors": errors,
    }


def run_checklist_timeline_checks(tmp_dir: Path) -> dict[str, Any]:
    contract_path = tmp_dir / "timeline_contract.json"
    output_dir = tmp_dir / "timeline_output"
    write_temp_json(
        contract_path,
        {
            "checks": [{"name": "always_fail", "command": "python3 -c 'import sys; sys.exit(1)'", "pass_condition": "exit_code_zero"}],
            "max_iterations": 4,
            "checklist_contract": {
                "run_id": "timeline-run",
                "items": [
                    {
                        "item_id": "strict-item",
                        "question": "Must pass check",
                        "evidence_required": ["iteration_log"],
                        "strictness": "strict",
                        "depends_on": [],
                        "status": "unsatisfied",
                        "satisfied_at_step": None,
                        "evidence_refs": [],
                        "pass_when_check": "always_fail",
                    }
                ],
                "termination_policy": "strict_gate",
                "reason_codes": [],
                "version": "1.0.0",
            },
        },
    )
    step = run_cmd(
        [
            sys.executable,
            str(RUN_UNTIL_GREEN),
            "--contract",
            str(contract_path),
            "--run-id",
            "timeline-run",
            "--output-dir",
            str(output_dir),
        ]
    )
    errors: list[str] = []
    parsed: dict[str, Any] = {}
    if step.get("stdout"):
        try:
            parsed = json.loads(step["stdout"])
        except json.JSONDecodeError:
            errors.append("timeline_stdout_not_json")
    if step["exit_code"] == 0:
        errors.append("timeline_should_fail_for_strict_item")
    if not parsed.get("strict_early_terminated", False):
        errors.append("strict_early_terminated_missing")
    if not Path(parsed.get("checklist_timeline_ref", "")).exists():
        errors.append("checklist_timeline_missing")
    if not isinstance(parsed.get("checklist_deltas", []), list):
        errors.append("checklist_deltas_missing")

    return {
        "name": "checklist_timeline_checks",
        "ok": step["exit_code"] != 0 and not errors,
        "details": [{**step, "expected_failure": True}],
        "errors": errors,
    }


def run_crw_authoritative_input_tests(tmp_dir: Path) -> dict[str, Any]:
    improved_in = tmp_dir / "reward_improved.json"
    proxy_only_in = tmp_dir / "reward_proxy_only.json"
    prr_only_in = tmp_dir / "reward_prr_only.json"
    improved_out = tmp_dir / "reward_improved_out.json"
    proxy_only_out = tmp_dir / "reward_proxy_only_out.json"
    prr_only_out = tmp_dir / "reward_prr_only_out.json"
    skill_result = {
        "ok": True,
        "outputs": {},
        "tool_calls": [],
        "cost_units": {"time_ms": 50.0, "tokens": 10, "cost_estimate": 0.0, "risk_class": "low"},
        "artefact_delta": {"files_changed": [], "tests_run": [], "urls_fetched": []},
        "progress_proxy": {"ran_tests": True},
        "failure_codes": [],
        "suggested_next": [],
    }
    budget_state = {"remaining_steps": 3, "remaining_time_ms": 2000, "repeated_actions_count": 0}
    write_temp_json(
        improved_in,
        {
            "run_id": "crw-improved",
            "skill_result": skill_result,
            "validator_state": {"all_passed": False, "improved": True, "progress_delta": 0.4, "reason_codes": []},
            "budget_state": budget_state,
            "progress_delta": 0.4,
            "reason_codes": [],
        },
    )
    write_temp_json(
        proxy_only_in,
        {
            "run_id": "crw-proxy-only",
            "skill_result": skill_result,
            "validator_state": {"all_passed": False, "improved": False, "progress_delta": 0.0, "reason_codes": []},
            "budget_state": budget_state,
            "progress_delta": 0.4,
            "reason_codes": [],
        },
    )
    write_temp_json(
        prr_only_in,
        {
            "run_id": "crw-prr-only",
            "skill_result": skill_result,
            "validator_state": {"all_passed": False, "improved": False, "progress_delta": 0.0, "reason_codes": []},
            "budget_state": budget_state,
            "progress_delta": 0.5,
            "project_run_reporter": {"narrative": "near pass, looks good"},
            "reason_codes": [],
        },
    )
    steps = [
        run_cmd([sys.executable, str(COMPUTE_CENTRAL_REWARD), "--input", str(improved_in), "--output", str(improved_out)]),
        run_cmd([sys.executable, str(COMPUTE_CENTRAL_REWARD), "--input", str(proxy_only_in), "--output", str(proxy_only_out)]),
        run_cmd([sys.executable, str(COMPUTE_CENTRAL_REWARD), "--input", str(prr_only_in), "--output", str(prr_only_out)]),
    ]
    errors: list[str] = []
    if all(step["ok"] for step in steps):
        improved_payload = read_json(improved_out)
        proxy_payload = read_json(proxy_only_out)
        prr_payload = read_json(prr_only_out)
        if float(improved_payload.get("reward_components", {}).get("progress_delta", 0.0)) <= 0.0:
            errors.append("improved_case_missing_positive_progress")
        if float(proxy_payload.get("reward_components", {}).get("progress_delta", -1.0)) != 0.0:
            errors.append("proxy_only_case_should_zero_progress")
        if float(prr_payload.get("reward_components", {}).get("progress_delta", -1.0)) != 0.0:
            errors.append("prr_narrative_should_not_increase_progress")
    return {
        "name": "crw_authoritative_input_tests",
        "ok": all(step["ok"] for step in steps) and not errors,
        "details": steps,
        "errors": errors,
    }


def run_distiller_proposal_schema_tests(tmp_dir: Path) -> dict[str, Any]:
    distiller_in = tmp_dir / "distiller_input.json"
    distiller_out = tmp_dir / "distiller_output.json"
    bad_in = tmp_dir / "distiller_bad_input.json"
    bad_out = tmp_dir / "distiller_bad_output.json"
    write_temp_json(
        distiller_in,
        {
            "skill_evolution_queue": [
                {
                    "queue_id": "q-001",
                    "task_signature": "routing-loop",
                    "target_skills": ["skill-picker-orchestrator"],
                    "reason_codes": ["no_progress/no_progress_loop"],
                    "missing_actions": ["switch_strategy"],
                    "candidate_change": "Force a strategy switch after two no-progress steps.",
                    "acceptance_tests": ["run_all_skill_checks --strict-skill-result"],
                    "rollback_plan": ["Revert patch if anti-loop regression appears."],
                    "evidence_refs": ["/tmp/rlm/run-01/trajectory.jsonl"],
                    "risk_class": "medium",
                    "confidence": 0.73,
                },
                {
                    "queue_id": "q-dup",
                    "task_signature": "routing-loop",
                    "target_skills": ["skill-picker-orchestrator"],
                    "reason_codes": ["no_progress/no_progress_loop"],
                    "missing_actions": ["switch_strategy"],
                    "candidate_change": "Duplicate entry should collapse.",
                    "evidence_refs": ["/tmp/rlm/run-01/trajectory.jsonl"],
                },
            ],
            "experience_packets": [{"task_signature": "routing-loop", "evidence_refs": ["/tmp/rlm/run-01/summary.json"]}],
            "failure_packets": [
                {
                    "task_signature": "routing-loop",
                    "reason_codes": ["no_progress/no_progress_loop"],
                    "missing_actions": ["switch_strategy"],
                    "minimal_repro_refs": ["/tmp/rlm/run-01/trajectory.jsonl"],
                }
            ],
        },
    )
    write_temp_json(
        bad_in,
        {
            "skill_evolution_queue": [
                {
                    "queue_id": "q-bad",
                    "task_signature": "missing-evidence-case",
                    "target_skills": ["validation-gate-runner"],
                }
            ],
            "experience_packets": [],
            "failure_packets": [],
        },
    )
    good = run_cmd([sys.executable, str(DISTILLER_SCRIPT), "--input", str(distiller_in), "--output", str(distiller_out)])
    bad = run_cmd([sys.executable, str(DISTILLER_SCRIPT), "--input", str(bad_in), "--output", str(bad_out)])
    errors: list[str] = []
    if good["ok"]:
        proposal_payload = read_json(distiller_out)
        schema = read_json(DISTILLER_PROPOSAL_SCHEMA)
        errors.extend([f"proposal_bundle.{key}" for key in validate_required_fields(proposal_payload, schema.get("required", []))])
        proposals = proposal_payload.get("proposals", [])
        if not isinstance(proposals, list) or not proposals:
            errors.append("proposal_bundle.proposals_empty")
        else:
            proposal_required = schema.get("properties", {}).get("proposals", {}).get("items", {}).get("required", [])
            if isinstance(proposal_required, list):
                for idx, proposal in enumerate(proposals):
                    if not isinstance(proposal, dict):
                        errors.append(f"proposal_not_object.{idx}")
                        continue
                    errors.extend([f"proposal[{idx}].{field}" for field in proposal_required if field not in proposal])
    else:
        errors.append("distiller_good_case_failed")
    if bad["exit_code"] == 0:
        errors.append("distiller_bad_case_should_fail_closed")
    return {
        "name": "distiller_proposal_schema_tests",
        "ok": good["ok"] and bad["exit_code"] != 0 and not errors,
        "details": [good, {**bad, "expected_failure": True}],
        "errors": errors,
    }


def run_anti_loop_behaviour_tests(tmp_dir: Path) -> dict[str, Any]:
    contract_path = tmp_dir / "anti_loop_contract.json"
    output_dir = tmp_dir / "anti_loop"
    write_temp_json(
        contract_path,
        {
            "checks": [{"name": "always_fail", "command": "python3 -c 'import sys; sys.exit(1)'", "pass_condition": "exit_code_zero"}],
            "max_iterations": 5,
        },
    )
    step = run_cmd(
        [
            sys.executable,
            str(RUN_UNTIL_GREEN),
            "--contract",
            str(contract_path),
            "--run-id",
            "anti-loop-smoke",
            "--output-dir",
            str(output_dir),
        ]
    )
    errors: list[str] = []
    parsed: dict[str, Any] = {}
    if step.get("stdout"):
        try:
            parsed = json.loads(step["stdout"])
        except json.JSONDecodeError:
            errors.append("anti_loop_stdout_not_json")
    if step["exit_code"] == 0:
        errors.append("anti_loop_case_should_fail")
    reason_codes = parsed.get("reason_codes", []) if isinstance(parsed, dict) else []
    if "no_progress/no_progress_loop" not in reason_codes:
        errors.append("missing_no_progress_reason_code")
    if parsed.get("strategy_switch_tag") != "stalled_no_progress":
        errors.append("missing_strategy_switch_tag")
    if not bool(parsed.get("diagnostic_ran", False)):
        errors.append("diagnostic_not_run")
    if not bool(parsed.get("aborted", False)):
        errors.append("anti_loop_should_abort_after_diagnostic")
    if "progress_summary" not in parsed or not isinstance(parsed.get("progress_summary"), dict):
        errors.append("missing_progress_summary")
    return {
        "name": "anti_loop_behaviour_tests",
        "ok": step["exit_code"] != 0 and not errors,
        "details": [{**step, "expected_failure": True}],
        "errors": errors,
    }


def run_ctx_namespace_compliance_checks(tmp_dir: Path) -> dict[str, Any]:
    input_root = tmp_dir / "ctx_input"
    output_root = tmp_dir / "ctx_output"
    input_root.mkdir(parents=True, exist_ok=True)
    (input_root / "a.txt").write_text("line one\\nline two\\n", encoding="utf-8")
    (input_root / "b.txt").write_text("line one\\nline two\\n", encoding="utf-8")
    init_step = run_cmd(
        [
            sys.executable,
            str(CTX_ADAPTER),
            "init",
            "--input-root",
            str(input_root),
            "--run-id",
            "ctx-run-smoke",
            "--output-dir",
            str(output_root),
        ]
    )
    inspect_step = run_cmd(
        [
            sys.executable,
            str(CTX_ADAPTER),
            "inspect",
            "--run-id",
            "ctx-run-smoke",
            "--output-dir",
            str(output_root),
            "--target",
            str(input_root / "a.txt"),
            "--operation",
            "peek",
            "--start",
            "1",
            "--end",
            "2",
        ]
    )
    nav_step = run_cmd(
        [
            sys.executable,
            str(CTX_NAV),
            "--input-root",
            str(input_root),
            "--run-id",
            "ctx-run-smoke",
            "--output-dir",
            str(output_root),
        ]
    )
    errors: list[str] = []
    if init_step["ok"] and nav_step["ok"]:
        manifest = read_json(output_root / "rlm" / "ctx-run-smoke" / "context_manifest.json")
        chunk_plan = read_json(output_root / "rlm" / "ctx-run-smoke" / "chunk_plan.json")
        for row in manifest.get("manifest", []):
            if row.get("run_id") != "ctx-run-smoke":
                errors.append("manifest_missing_run_id")
            if not str(row.get("namespace", "")).startswith("ctx://run/"):
                errors.append("manifest_missing_namespace")
            if "dedup_hash" not in row:
                errors.append("manifest_missing_dedup_hash")
            if not isinstance(row.get("retention"), dict):
                errors.append("manifest_missing_retention")
            if bool(row.get("blessed_for_long_term", True)):
                errors.append("manifest_unexpected_long_term_blessing")
        for row in chunk_plan.get("chunks", []):
            if row.get("run_id") != "ctx-run-smoke":
                errors.append("chunk_missing_run_id")
            if "dedup_hash" not in row:
                errors.append("chunk_missing_dedup_hash")
    else:
        errors.append("ctx_commands_failed")
    return {
        "name": "ctx_namespace_compliance_checks",
        "ok": init_step["ok"] and inspect_step["ok"] and nav_step["ok"] and not errors,
        "details": [init_step, inspect_step, nav_step],
        "errors": errors,
    }


def run_simulated_lane_contract_checks(tmp_dir: Path) -> dict[str, Any]:
    sandbox_in = tmp_dir / "sandbox_simulated.json"
    sandbox_out = tmp_dir / "sandbox_simulated_out.json"
    deploy_out = tmp_dir / "deploy"
    verify_report = tmp_dir / "deploy" / "verify_simulated.md"
    write_temp_json(
        sandbox_in,
        {
            "run_id": "lane-smoke",
            "trust_level": "untrusted",
            "requested_profile": "simulated_tools",
            "simulation_policy": "deterministic_stub",
            "audit_ref": "/tmp/deploy/lane-smoke-audit.json",
        },
    )
    sandbox_step = run_cmd([sys.executable, str(SANDBOX_PROFILE), "--input", str(sandbox_in), "--output", str(sandbox_out)])
    deploy_step = run_cmd(
        [
            str(CODEX_ROOT / "deploy-verify-loop/scripts/run_deploy_loop.sh"),
            "--run-id",
            "lane-smoke",
            "--deploy-confirmed",
            "true",
            "--output-dir",
            str(deploy_out),
            "--enable-simulated-lane",
            "true",
            "--enable-real-lane",
            "true",
        ]
    )
    verify_step = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "deploy-verify-loop/scripts/verify_live_endpoint.py"),
            "--url",
            "https://example.com",
            "--run-id",
            "lane-smoke",
            "--output",
            str(verify_report),
            "--lane-id",
            "simulated",
            "--provenance-tag",
            "simulated",
        ]
    )
    errors: list[str] = []
    if sandbox_step["ok"]:
        payload = read_json(sandbox_out)
        if not payload.get("simulated", False):
            errors.append("sandbox_missing_simulated_flag")
        if payload.get("provenance_tag") != "simulated":
            errors.append("sandbox_missing_simulated_provenance")
    else:
        errors.append("sandbox_step_failed")
    lane_delta = deploy_out / "lane_delta_summary.json"
    if not lane_delta.exists():
        errors.append("missing_lane_delta_summary")
    if not verify_step["ok"]:
        errors.append("verify_step_failed")
    return {
        "name": "simulated_lane_contract_checks",
        "ok": sandbox_step["ok"] and deploy_step["ok"] and verify_step["ok"] and not errors,
        "details": [sandbox_step, deploy_step, verify_step],
        "errors": errors,
    }


def run_progress_proxy_credit_checks(tmp_dir: Path) -> dict[str, Any]:
    good_in = tmp_dir / "progress_good.json"
    stall_in = tmp_dir / "progress_stall.json"
    good_out = tmp_dir / "progress_good_out.json"
    stall_out = tmp_dir / "progress_stall_out.json"
    write_temp_json(
        good_in,
        {"checklist_delta_score": 0.4, "evidence_coverage_delta": 0.3, "unresolved_questions_delta": 0.2, "stall_threshold": 0.0},
    )
    write_temp_json(
        stall_in,
        {"checklist_delta_score": 0.0, "evidence_coverage_delta": 0.0, "unresolved_questions_delta": -0.1, "stall_threshold": 0.0},
    )
    good_step = run_cmd([sys.executable, str(COMPUTE_PROGRESS_PROXY), "--input", str(good_in), "--output", str(good_out)])
    stall_step = run_cmd([sys.executable, str(COMPUTE_PROGRESS_PROXY), "--input", str(stall_in), "--output", str(stall_out)])
    errors: list[str] = []
    if good_step["ok"] and stall_step["ok"]:
        good_payload = read_json(good_out).get("progress_proxy_v2", {})
        stall_payload = read_json(stall_out).get("progress_proxy_v2", {})
        if float(good_payload.get("composite_score", 0.0)) <= 0.0:
            errors.append("good_progress_proxy_non_positive")
        if not bool(stall_payload.get("stalled", False)):
            errors.append("stall_progress_proxy_not_stalled")
    else:
        errors.append("progress_proxy_steps_failed")
    return {
        "name": "progress_proxy_credit_checks",
        "ok": good_step["ok"] and stall_step["ok"] and not errors,
        "details": [good_step, stall_step],
        "errors": errors,
    }


def run_snapshot_index_checks(tmp_dir: Path) -> dict[str, Any]:
    source_events = tmp_dir / "snapshots.json"
    snapshot_index = tmp_dir / "snapshot_index.json"
    grounding_claims = tmp_dir / "claims.json"
    grounding_out = tmp_dir / "grounding_snapshot.json"
    write_temp_json(
        source_events,
        [
            {
                "snapshot_id": "snap-001",
                "url": "https://example.com/a",
                "captured_at": "2026-02-13T00:00:00Z",
                "dom_text": "claim one evidence",
                "viewport_hint": "hero",
                "screenshot_path": "/tmp/snap-001.png",
                "candidate_evidence_spans": [{"text": "claim one evidence"}],
                "source_type": "snapshot_visual",
                "provenance_tag": "real",
            },
            {
                "snapshot_id": "snap-002",
                "url": "https://example.com/b",
                "captured_at": "2026-02-13T00:00:01Z",
                "dom_text": "simulated evidence",
                "viewport_hint": "body",
                "screenshot_path": "/tmp/snap-002.png",
                "candidate_evidence_spans": [{"text": "simulated evidence"}],
                "source_type": "dom_text",
                "provenance_tag": "simulated",
            },
        ],
    )
    write_temp_json(grounding_claims, [{"claim_id": "claim-1", "snapshot_ids": ["snap-001", "snap-002"]}])

    build_step = run_cmd(
        [
            sys.executable,
            str(BUILD_SNAPSHOT_INDEX),
            "--run-id",
            "snapshot-smoke",
            "--input",
            str(source_events),
            "--output",
            str(snapshot_index),
        ]
    )
    grounding_step = run_cmd(
        [
            sys.executable,
            str(VALIDATE_SNAPSHOT_GROUNDING),
            "--claims",
            str(grounding_claims),
            "--snapshot-index",
            str(snapshot_index),
            "--output",
            str(grounding_out),
            "--min-independent",
            "1",
        ]
    )
    errors: list[str] = []
    try:
        schema = read_json(SNAPSHOT_INDEX_SCHEMA)
        payload = read_json(snapshot_index)
        errors.extend([f"snapshot_index.{key}" for key in validate_required_fields(payload, schema.get("required", []))])
        entries = payload.get("entries", []) if isinstance(payload.get("entries", []), list) else []
        item_required = schema.get("properties", {}).get("entries", {}).get("items", {}).get("required", [])
        if isinstance(item_required, list):
            for idx, row in enumerate(entries):
                if not isinstance(row, dict):
                    errors.append(f"snapshot_index.entries[{idx}]_not_object")
                    continue
                for key in item_required:
                    if key not in row:
                        errors.append(f"snapshot_index.entries[{idx}].{key}")
    except Exception:
        errors.append("snapshot_schema_validation_failed")

    if not grounding_step["ok"]:
        errors.append("snapshot_grounding_failed")

    return {
        "name": "snapshot_index_checks",
        "ok": build_step["ok"] and grounding_step["ok"] and not errors,
        "details": [build_step, grounding_step],
        "errors": errors,
    }


def run_evidence_object_contract_checks(tmp_dir: Path) -> dict[str, Any]:
    schema = read_json(EVIDENCE_OBJECT_SCHEMA)
    valid = {
        "source": "pdf",
        "location": {"path": "/tmp/doc.pdf", "page": 3},
        "span": "Evidence text",
        "confidence": 0.72,
        "provenance_tag": "real",
    }
    invalid = {"source": "pdf", "location": "/tmp/doc.pdf", "span": "bad", "confidence": 2.4}
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in valid:
            errors.append(f"valid_missing_required.{key}")
    if isinstance(invalid.get("location"), dict):
        errors.append("invalid_location_type_not_detected")
    if not (0.0 <= float(valid.get("confidence", 0.0)) <= 1.0):
        errors.append("valid_confidence_range_failed")
    if not (0.0 <= float(invalid.get("confidence", 0.0)) <= 1.0):
        pass
    else:
        errors.append("invalid_confidence_not_detected")
    return {
        "name": "evidence_object_contract_checks",
        "ok": not errors,
        "details": [{"schema": str(EVIDENCE_OBJECT_SCHEMA)}],
        "errors": errors,
    }


def run_output_boundary_limit_checks(tmp_dir: Path) -> dict[str, Any]:
    limits = read_json(OUTPUT_BOUNDARY_LIMITS)
    payload_ok = {"payload": {"items": [1, 2, 3], "text": "ok"}, "validate_evidence_objects": False}
    payload_bad = {
        "payload": {
            "items": list(range(int(limits.get("max_array_items", 200)) + 1)),
            "text": "x" * (int(limits.get("max_text_field_bytes", 65536)) + 1),
        },
        "validate_evidence_objects": False,
    }
    in_ok = tmp_dir / "boundary_ok.json"
    in_bad = tmp_dir / "boundary_bad.json"
    out_ok = tmp_dir / "boundary_ok_out.json"
    out_bad = tmp_dir / "boundary_bad_out.json"
    write_temp_json(in_ok, payload_ok)
    write_temp_json(in_bad, payload_bad)
    ok_step = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "tool-contract-enforcer/scripts/run_tool_contract_enforcer.py"),
            "--input",
            str(in_ok),
            "--output",
            str(out_ok),
            "--strict-output-boundaries",
        ]
    )
    bad_step = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "tool-contract-enforcer/scripts/run_tool_contract_enforcer.py"),
            "--input",
            str(in_bad),
            "--output",
            str(out_bad),
            "--strict-output-boundaries",
        ]
    )
    errors: list[str] = []
    if not ok_step["ok"]:
        errors.append("boundary_ok_should_pass")
    if bad_step["exit_code"] == 0:
        errors.append("boundary_bad_should_fail")
    return {
        "name": "output_boundary_limit_checks",
        "ok": ok_step["ok"] and bad_step["exit_code"] != 0 and not errors,
        "details": [ok_step, {**bad_step, "expected_failure": True}],
        "errors": errors,
    }


def run_deterministic_preflight_policy_checks(tmp_dir: Path) -> dict[str, Any]:
    route_task = tmp_dir / "route_task_preflight.json"
    route_out = tmp_dir / "route_out_preflight.json"
    write_temp_json(
        route_task,
        {
            "task_description": "verify deterministic route",
            "task_signature": "deterministic-route",
            "deterministic_check_command": "python3 -c 'print(1)'",
        },
    )
    step = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "skill-picker-orchestrator/scripts/route_task.py"),
            "--task-json",
            str(route_task),
            "--skills-root",
            str(CODEX_ROOT),
            "--scratchpad",
            str(tmp_dir / "scratchpad.md"),
            "--project-root",
            str(CODEX_ROOT),
            "--output",
            str(route_out),
        ]
    )
    errors: list[str] = []
    if step["ok"]:
        payload = read_json(route_out)
        preflight = payload.get("deterministic_preflight", {})
        flags = payload.get("routing_policy_flags", {})
        if not bool(preflight.get("attempted", False)):
            errors.append("deterministic_preflight_not_attempted")
        if preflight.get("result") != "planned":
            errors.append("deterministic_preflight_not_planned")
        if not bool(flags.get("deterministic_first_default", False)):
            errors.append("deterministic_first_flag_missing")
    else:
        errors.append("route_task_failed")
    return {
        "name": "deterministic_preflight_policy_checks",
        "ok": step["ok"] and not errors,
        "details": [step],
        "errors": errors,
    }


def run_execution_audit_contract_checks(tmp_dir: Path) -> dict[str, Any]:
    good_in = tmp_dir / "sandbox_audit_good.json"
    bad_in = tmp_dir / "sandbox_audit_bad.json"
    good_out = tmp_dir / "sandbox_audit_good_out.json"
    bad_out = tmp_dir / "sandbox_audit_bad_out.json"
    write_temp_json(
        good_in,
        {
            "run_id": "audit-run",
            "trust_level": "generated_untrusted",
            "requested_profile": "docker",
            "audit_ref": "/tmp/audit/audit-run.json",
        },
    )
    write_temp_json(
        bad_in,
        {
            "run_id": "audit-run",
            "trust_level": "generated_untrusted",
            "requested_profile": "docker",
            "audit_ref": "",
        },
    )
    good_step = run_cmd([sys.executable, str(SANDBOX_PROFILE), "--input", str(good_in), "--output", str(good_out)])
    bad_step = run_cmd([sys.executable, str(SANDBOX_PROFILE), "--input", str(bad_in), "--output", str(bad_out)])
    errors: list[str] = []
    if not good_step["ok"]:
        errors.append("execution_audit_good_should_pass")
    if bad_step["exit_code"] == 0:
        errors.append("execution_audit_bad_should_fail")
    return {
        "name": "execution_audit_contract_checks",
        "ok": good_step["ok"] and bad_step["exit_code"] != 0 and not errors,
        "details": [good_step, {**bad_step, "expected_failure": True}],
        "errors": errors,
    }


def run_self_correction_no_regression_checks(tmp_dir: Path) -> dict[str, Any]:
    contract_ok = tmp_dir / "sc_no_regress_ok_contract.json"
    contract_bad = tmp_dir / "sc_no_regress_bad_contract.json"
    out_ok = tmp_dir / "sc_no_regress_ok_out"
    out_bad = tmp_dir / "sc_no_regress_bad_out"
    write_temp_json(
        contract_ok,
        {
            "run_id": "sc-ok",
            "checks": [{"name": "noop", "command": "true", "pass_condition": "exit_code_zero"}],
            "max_iterations": 1,
            "correction_rollout": {
                "run_id": "sc-ok",
                "task_signature": "self-correction-no-regress",
                "attempt_1": "first",
                "attempt_2": "second",
                "validator_score_o1": 1.0,
                "validator_score_o2": 1.0,
                "improvement_delta": 0.0,
                "evidence_refs": ["/tmp/evidence.json"],
            },
        },
    )
    write_temp_json(
        contract_bad,
        {
            "run_id": "sc-bad",
            "checks": [{"name": "noop", "command": "true", "pass_condition": "exit_code_zero"}],
            "max_iterations": 1,
            "correction_rollout": {
                "run_id": "sc-bad",
                "task_signature": "self-correction-regress",
                "attempt_1": "first",
                "attempt_2": "second",
                "validator_score_o1": 1.0,
                "validator_score_o2": 0.0,
                "improvement_delta": -1.0,
                "evidence_refs": ["/tmp/evidence.json"],
            },
        },
    )
    ok_step = run_cmd(
        [
            sys.executable,
            str(RUN_UNTIL_GREEN),
            "--contract",
            str(contract_ok),
            "--run-id",
            "sc-ok",
            "--output-dir",
            str(out_ok),
        ]
    )
    bad_step = run_cmd(
        [
            sys.executable,
            str(RUN_UNTIL_GREEN),
            "--contract",
            str(contract_bad),
            "--run-id",
            "sc-bad",
            "--output-dir",
            str(out_bad),
        ]
    )
    errors: list[str] = []
    if not ok_step["ok"]:
        errors.append("self_correction_no_regression_expected_pass")
    if bad_step["exit_code"] == 0:
        errors.append("self_correction_regression_expected_fail")
    else:
        parsed = json.loads(bad_step["stdout"]) if bad_step.get("stdout") else {}
        codes = parsed.get("reason_codes", []) if isinstance(parsed, dict) else []
        if "validation_failed/self_correction_regressed" not in codes:
            errors.append("self_correction_regression_reason_code_missing")
    return {
        "name": "self_correction_no_regression_checks",
        "ok": not errors,
        "details": [ok_step, {**bad_step, "expected_failure": True}],
        "errors": errors,
    }


def run_letta_pointer_contract_checks(tmp_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not LETTA_POINTER_CONTRACT_SCHEMA.exists():
        return {
            "name": "letta_pointer_contract_checks",
            "ok": False,
            "details": [],
            "errors": ["missing_schema.letta_pointer_contract_schema"],
        }
    schema = read_json(LETTA_POINTER_CONTRACT_SCHEMA)
    valid_sample = {
        "provider": "letta",
        "folder_id": "folder-001",
        "document_id": "doc-001",
        "source_uri": "letta://folder-001/doc-001",
        "content_hash": "sha256:abc123",
        "synced_at_unix": 1730000000,
        "provenance_tag": "real",
    }
    missing_sample = {
        "provider": "letta",
        "folder_id": "folder-001",
        "source_uri": "letta://folder-001/doc-001",
        "synced_at_unix": 1730000000,
        "provenance_tag": "real",
    }
    required = schema.get("required", []) if isinstance(schema, dict) else []
    valid_missing = validate_required_fields(valid_sample, required)
    invalid_missing = validate_required_fields(missing_sample, required)
    if valid_missing:
        errors.append("valid_sample_missing_required")
    if "document_id" not in invalid_missing or "content_hash" not in invalid_missing:
        errors.append("missing_required_not_detected")
    taxonomy = read_json(REASON_TAXONOMY) if REASON_TAXONOMY.exists() else {}
    codes = taxonomy.get("codes", {}) if isinstance(taxonomy, dict) else {}
    available = set(codes.keys()) if isinstance(codes, dict) else set()
    required_codes = {
        "schema_violation/letta_pointer_missing_required",
        "schema_violation/letta_pointer_invalid_type",
        "validation_failed/letta_pointer_hash_missing",
        "validation_failed/letta_pointer_stale_sync",
        "policy_violation/letta_direct_memory_write_forbidden",
    }
    missing_codes = sorted(code for code in required_codes if code not in available)
    if missing_codes:
        errors.append("taxonomy_missing_letta_codes")
    return {
        "name": "letta_pointer_contract_checks",
        "ok": not errors,
        "details": [
            {
                "schema_path": str(LETTA_POINTER_CONTRACT_SCHEMA),
                "missing_codes": missing_codes,
            }
        ],
        "errors": errors,
    }


def run_context_repo_contract_checks(tmp_dir: Path) -> dict[str, Any]:
    repo_root = CODEX_ROOT / "memory_repo"
    errors: list[str] = []
    required_dirs = ["system", "domain", "tasks", "ops", ".meta"]
    for dirname in required_dirs:
        if not (repo_root / dirname).exists():
            errors.append(f"missing_dir.{dirname}")
    if not (repo_root / ".git").exists():
        errors.append("missing_git_repo")

    template = repo_root / ".meta/templates/memory_entry.md"
    if not template.exists():
        errors.append("missing_template")

    schema = read_json(CONTEXT_REPO_CONTRACT_SCHEMA)
    sample = {
        "repo_root": str(repo_root),
        "run_id": "context-smoke",
        "layout": {key: str(repo_root / key) for key in required_dirs},
        "worktree_policy": {"mandatory_for_memory_write": True},
        "commit_policy": {"commit_per_update": True},
        "defrag_policy": {"max_files": 25},
        "external_context_policy": {
            "mode": "read_only_mirror",
            "authority": "git_memory_repo",
            "direct_external_writes_forbidden": True,
        },
        "pointer_contract_ref": str(LETTA_POINTER_CONTRACT_SCHEMA),
    }
    errors.extend([f"context_contract.{key}" for key in validate_required_fields(sample, schema.get("required", []))])
    return {
        "name": "context_repo_contract_checks",
        "ok": not errors,
        "details": [{"repo_root": str(repo_root)}],
        "errors": errors,
    }


def run_memory_migration_checks(tmp_dir: Path) -> dict[str, Any]:
    scratchpad = tmp_dir / "scratchpad.md"
    repo_root = tmp_dir / "memory_repo"
    for dirname in ("system", "domain", "tasks", "ops", ".meta"):
        (repo_root / dirname).mkdir(parents=True, exist_ok=True)
    run_cmd(["git", "-C", str(repo_root), "init"])
    scratchpad.write_text(
        "\n\n".join(
            [
                "failure_mode: no_progress_loop\nreason_codes: [no_progress/no_progress_loop]\nconfidence: 0.9",
                "best_skill_stack: [validation-gate-runner, self-correction-loop]\nrecommended_sequence: run checks then switch",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_dir / "migration_out.json"
    step = run_cmd(
        [
            sys.executable,
            str(MIGRATE_STABLE_PATTERNS),
            "--scratchpad",
            str(scratchpad),
            "--repo-root",
            str(repo_root),
            "--output",
            str(output),
        ]
    )
    errors: list[str] = []
    if step["ok"]:
        payload = read_json(output)
        if int(payload.get("migrated_count", 0)) < 1:
            errors.append("expected_migration_count_gt_zero")
    else:
        errors.append("migration_script_failed")
    return {"name": "migration_correctness_checks", "ok": step["ok"] and not errors, "details": [step], "errors": errors}


def run_memory_worktree_enforcement_checks(tmp_dir: Path) -> dict[str, Any]:
    assignments = tmp_dir / "assignments.json"
    worktrees_root = tmp_dir / "worktrees"
    out_path = tmp_dir / "created_worktrees.json"
    write_temp_json(
        assignments,
        {"assignments": [{"step_id": "memory-1", "task_tag": "memory_write"}, {"step_id": "normal-1", "task_tag": "general"}]},
    )
    create_step = run_cmd(
        [
            sys.executable,
            str(CREATE_MEMORY_WORKTREES),
            "--assignments",
            str(assignments),
            "--worktrees-root",
            str(worktrees_root),
            "--output",
            str(out_path),
        ]
    )
    merge_in = tmp_dir / "merge_candidates.json"
    merge_out = tmp_dir / "merge_out.json"
    write_temp_json(
        merge_in,
        {"candidates": [{"candidate_id": "c1", "validation_passed": True, "governor_approved": True}, {"candidate_id": "c2", "validation_passed": False, "governor_approved": True}]},
    )
    merge_step = run_cmd(
        [
            sys.executable,
            str(MERGE_MEMORY_WORKTREE_CANDIDATES),
            "--input",
            str(merge_in),
            "--output",
            str(merge_out),
        ]
    )
    errors: list[str] = []
    if create_step["ok"]:
        payload = read_json(out_path)
        if int(len(payload.get("created_worktrees", []))) < 1:
            errors.append("worktree_not_created")
    else:
        errors.append("create_worktree_failed")
    if not merge_step["ok"]:
        errors.append("merge_candidates_failed")
    return {
        "name": "memory_worktree_checks",
        "ok": create_step["ok"] and merge_step["ok"] and not errors,
        "details": [create_step, merge_step],
        "errors": errors,
    }


def run_memory_defrag_safety_checks(tmp_dir: Path) -> dict[str, Any]:
    out = tmp_dir / "defrag_out.json"
    step = run_cmd([sys.executable, str(DEFRAG_MEMORY_REPO), "--output", str(out)])
    errors: list[str] = []
    if step["ok"]:
        payload = read_json(out)
        if not isinstance(payload.get("relocation_pointers", []), list):
            errors.append("missing_relocation_pointers")
    else:
        errors.append("defrag_failed")
    return {"name": "memory_defrag_safety_checks", "ok": step["ok"] and not errors, "details": [step], "errors": errors}


def run_retrieval_budget_compliance_checks(tmp_dir: Path) -> dict[str, Any]:
    task = tmp_dir / "route_task.json"
    out = tmp_dir / "route_out.json"
    write_temp_json(
        task,
        {"task_description": "memory heavy task", "task_signature": "memory-heavy", "memory_top_k": 5},
    )
    step = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "skill-picker-orchestrator/scripts/route_task.py"),
            "--task-json",
            str(task),
            "--skills-root",
            str(CODEX_ROOT),
            "--scratchpad",
            str(tmp_dir / "scratchpad.md"),
            "--project-root",
            str(CODEX_ROOT),
            "--output",
            str(out),
        ]
    )
    errors: list[str] = []
    if step["ok"]:
        payload = read_json(out)
        memory = payload.get("memory_retrieval", {})
        if int(memory.get("retrieval_top_k", 0)) != 5:
            errors.append("topk_not_5")
        if len(memory.get("retrieved_top_k", [])) > 5:
            errors.append("retrieved_over_budget")
    else:
        errors.append("route_task_failed")
    return {"name": "retrieval_budget_compliance_checks", "ok": step["ok"] and not errors, "details": [step], "errors": errors}


def _list_top_level_skills(skills_root: Path) -> list[str]:
    skills: list[str] = []
    for child in sorted(skills_root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            skills.append(child.name)
    return skills


def _extract_skill_description(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    for raw in parts[1].splitlines():
        line = raw.strip()
        if not line.startswith("description:"):
            continue
        return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def run_skill_invocation_smoke_checks(tmp_dir: Path) -> dict[str, Any]:
    skills = _list_top_level_skills(CODEX_ROOT)
    route_script = CODEX_ROOT / "skill-picker-orchestrator/scripts/route_task.py"
    errors: list[str] = []
    details: list[dict[str, Any]] = []
    all_gate_overrides: dict[str, Any] = {
        "ambiguity_unresolved": True,
        "local_context_reviewed": True,
        "source_grounding_done": True,
        "browser_context_applicable": False,
        "browser_context_done": False,
        "needs_cross_repo": True,
        "attached_repos": ["repo-a"],
        "deploy_requested": True,
        "idle_allow_list_enabled": True,
        "idle_allowed_task_classes": ["maintenance"],
        "independent_branches": 2,
        "max_triggered_skills": max(5, len(skills)),
    }

    explicit_misses: list[str] = []
    description_misses: list[str] = []
    missing_descriptions: list[str] = []
    route_failures: list[str] = []

    for skill in skills:
        explicit_task_path = tmp_dir / f"route_explicit_{skill}.json"
        explicit_out_path = tmp_dir / f"route_explicit_{skill}_out.json"
        write_temp_json(
            explicit_task_path,
            {
                "task_description": f"Please use ${skill} for this task.",
                "task_signature": f"explicit-{skill}",
                **all_gate_overrides,
            },
        )
        explicit_step = run_cmd(
            [
                sys.executable,
                str(route_script),
                "--task-json",
                str(explicit_task_path),
                "--skills-root",
                str(CODEX_ROOT),
                "--scratchpad",
                str(tmp_dir / "scratchpad.md"),
                "--project-root",
                str(CODEX_ROOT),
                "--output",
                str(explicit_out_path),
            ]
        )
        if not explicit_step["ok"]:
            route_failures.append(f"explicit:{skill}")
            continue
        explicit_payload = read_json(explicit_out_path)
        explicit_chosen = explicit_payload.get("chosen_skills", [])
        if not isinstance(explicit_chosen, list) or skill not in explicit_chosen:
            explicit_misses.append(skill)

        desc = _extract_skill_description(CODEX_ROOT / skill / "SKILL.md")
        if not desc:
            missing_descriptions.append(skill)
            continue

        description_task_path = tmp_dir / f"route_description_{skill}.json"
        description_out_path = tmp_dir / f"route_description_{skill}_out.json"
        write_temp_json(
            description_task_path,
            {
                "task_description": desc,
                "task_signature": f"description-{skill}",
                **all_gate_overrides,
            },
        )
        description_step = run_cmd(
            [
                sys.executable,
                str(route_script),
                "--task-json",
                str(description_task_path),
                "--skills-root",
                str(CODEX_ROOT),
                "--scratchpad",
                str(tmp_dir / "scratchpad.md"),
                "--project-root",
                str(CODEX_ROOT),
                "--output",
                str(description_out_path),
            ]
        )
        if not description_step["ok"]:
            route_failures.append(f"description:{skill}")
            continue
        description_payload = read_json(description_out_path)
        description_chosen = description_payload.get("chosen_skills", [])
        if not isinstance(description_chosen, list) or skill not in description_chosen:
            description_misses.append(skill)

    if explicit_misses:
        errors.append("explicit_skill_invocation_miss")
    if description_misses:
        errors.append("description_intent_invocation_miss")
    if missing_descriptions:
        errors.append("missing_skill_description_frontmatter")
    if route_failures:
        errors.append("route_task_failed")

    details.append(
        {
            "skills_count": len(skills),
            "explicit_miss_count": len(explicit_misses),
            "description_miss_count": len(description_misses),
            "missing_description_count": len(missing_descriptions),
            "route_failure_count": len(route_failures),
            "explicit_misses": explicit_misses[:30],
            "description_misses": description_misses[:30],
            "missing_descriptions": missing_descriptions[:30],
            "route_failures": route_failures[:30],
        }
    )
    return {
        "name": "skill_invocation_smoke_checks",
        "ok": not errors,
        "details": details,
        "errors": errors,
    }


def _run_route_task(tmp_dir: Path, task_payload: dict[str, Any], out_name: str, env: dict[str, str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    task_path = tmp_dir / f"{out_name}.task.json"
    out_path = tmp_dir / f"{out_name}.route.json"
    write_temp_json(task_path, task_payload)
    step = run_cmd(
        [
            sys.executable,
            str(CODEX_ROOT / "skill-picker-orchestrator/scripts/route_task.py"),
            "--task-json",
            str(task_path),
            "--skills-root",
            str(CODEX_ROOT),
            "--scratchpad",
            str(tmp_dir / "scratchpad.md"),
            "--project-root",
            str(CODEX_ROOT),
            "--output",
            str(out_path),
        ],
        env=env,
    )
    payload = read_json(out_path) if step["ok"] and out_path.exists() else {}
    return step, payload


def run_letta_sync_preflight_checks(tmp_dir: Path) -> dict[str, Any]:
    cache_root = tmp_dir / "letta_cache_sync"
    env = {
        "LETTA_RUNTIME_ENABLED": "1",
        "LETTA_AGENT_ID": "agent-smoke-sync",
        "LETTA_SIMULATE": "ok",
        "LETTA_SYNC_TTL_SECONDS": "1",
        "LETTA_CACHE_ROOT": str(cache_root),
    }
    step, payload = _run_route_task(
        tmp_dir,
        {
            "task_description": "verify letta preflight sync",
            "task_signature": "letta-sync-preflight",
            "project_root": str(CODEX_ROOT),
            "project_id": "project-smoke",
        },
        "letta_sync_preflight",
        env=env,
    )
    errors: list[str] = []
    letta = payload.get("memory_retrieval", {}).get("letta", {}) if isinstance(payload, dict) else {}
    if not step["ok"]:
        errors.append("route_task_failed")
    if not bool(letta.get("enabled", False)):
        errors.append("letta_not_enabled")
    if str(letta.get("sync_status", "")) not in {"ok", "degraded"}:
        errors.append("letta_sync_status_invalid")
    if "reason_codes" not in letta or not isinstance(letta.get("reason_codes"), list):
        errors.append("letta_reason_codes_missing")
    return {"name": "letta_sync_preflight_checks", "ok": not errors, "details": [step], "errors": errors}


def run_letta_hybrid_retrieval_checks(tmp_dir: Path) -> dict[str, Any]:
    simulated_items = [
        {
            "folder_id": "sim",
            "document_id": "proj-hit",
            "summary": "memory heavy task exact project hit",
            "project_id": "proj-a",
        },
        {
            "folder_id": "sim",
            "document_id": "other-hit",
            "summary": "memory heavy task unrelated",
            "project_id": "proj-b",
        },
    ]
    cache_root = tmp_dir / "letta_cache_hybrid"
    env = {
        "LETTA_RUNTIME_ENABLED": "1",
        "LETTA_AGENT_ID": "agent-smoke-hybrid",
        "LETTA_SIMULATE": "ok",
        "LETTA_SIMULATE_ITEMS": json.dumps(simulated_items, ensure_ascii=True),
        "LETTA_CACHE_ROOT": str(cache_root),
    }
    step, payload = _run_route_task(
        tmp_dir,
        {
            "task_description": "memory heavy task exact project hit",
            "task_signature": "letta-hybrid-retrieval",
            "project_root": str(CODEX_ROOT),
            "project_id": "proj-a",
            "memory_top_k": 3,
        },
        "letta_hybrid_retrieval",
        env=env,
    )
    errors: list[str] = []
    memory = payload.get("memory_retrieval", {}) if isinstance(payload, dict) else {}
    letta = memory.get("letta", {}) if isinstance(memory, dict) else {}
    selected = letta.get("items_selected", []) if isinstance(letta.get("items_selected", []), list) else []
    merged = memory.get("retrieved_top_k", []) if isinstance(memory.get("retrieved_top_k", []), list) else []
    if not step["ok"]:
        errors.append("route_task_failed")
    if len(merged) > int(memory.get("retrieval_top_k", 0) or 0):
        errors.append("hybrid_over_budget")
    if not selected:
        errors.append("no_letta_items_selected")
    if selected and "proj-hit" not in selected[0]:
        errors.append("project_boost_not_applied")
    return {"name": "letta_hybrid_retrieval_checks", "ok": not errors, "details": [step], "errors": errors}


def run_letta_staged_publish_checks(tmp_dir: Path) -> dict[str, Any]:
    stage_in = tmp_dir / "letta_stage_in.json"
    stage_out = tmp_dir / "letta_stage_out.json"
    publish_in = tmp_dir / "letta_publish_in.json"
    publish_out = tmp_dir / "letta_publish_out.json"
    run_id = "letta-stage-publish-smoke"
    write_temp_json(
        stage_in,
        {
            "run_id": run_id,
            "agent_id": "agent-smoke",
            "project_id": "proj-a",
            "drafts": [
                {
                    "source_pointers": ["/tmp/source-a.json"],
                    "summary": "staged draft summary",
                    "provenance_tag": "real",
                    "created_at_unix": int(time.time()),
                    "confidence": 0.8,
                }
            ],
        },
    )
    stage_step = run_cmd([sys.executable, str(STAGE_LETTA_DRAFT), "--input", str(stage_in), "--output", str(stage_out)])
    staged_payload = read_json(stage_out) if stage_step["ok"] and stage_out.exists() else {}

    write_temp_json(
        publish_in,
        {
            "run_id": run_id,
            "agent_id": "agent-smoke",
            "project_id": "proj-a",
            "validator_passed": True,
            "governor_approved": True,
            "draft_queue_ref": staged_payload.get("draft_queue_ref", ""),
        },
    )
    publish_step = run_cmd(
        [sys.executable, str(PUBLISH_LETTA_DRAFTS), "--input", str(publish_in), "--output", str(publish_out)],
        env={"LETTA_RUNTIME_ENABLED": "1", "LETTA_AGENT_ID": "agent-smoke", "LETTA_SIMULATE": "ok", "LETTA_PUBLISH_ENABLED": "1"},
    )
    publish_payload = read_json(publish_out) if publish_step["ok"] and publish_out.exists() else {}

    errors: list[str] = []
    if not stage_step["ok"]:
        errors.append("stage_failed")
    if not publish_step["ok"]:
        errors.append("publish_failed")
    if int(publish_payload.get("published_count", 0)) < 1:
        errors.append("published_count_zero")
    pointers = publish_payload.get("external_context_pointers", [])
    if not isinstance(pointers, list) or not pointers:
        errors.append("publish_pointers_missing")
    return {"name": "letta_staged_publish_checks", "ok": not errors, "details": [stage_step, publish_step], "errors": errors}


def run_letta_fail_open_checks(tmp_dir: Path) -> dict[str, Any]:
    cache_root = tmp_dir / "letta_cache_fail_open"
    env = {
        "LETTA_RUNTIME_ENABLED": "1",
        "LETTA_AGENT_ID": "agent-smoke-fail",
        "LETTA_SIMULATE": "fail",
        "LETTA_CACHE_ROOT": str(cache_root),
    }
    step, payload = _run_route_task(
        tmp_dir,
        {
            "task_description": "memory heavy task",
            "task_signature": "letta-fail-open",
            "project_root": str(CODEX_ROOT),
            "project_id": "proj-a",
            "memory_top_k": 3,
        },
        "letta_fail_open",
        env=env,
    )
    errors: list[str] = []
    memory = payload.get("memory_retrieval", {}) if isinstance(payload, dict) else {}
    letta = memory.get("letta", {}) if isinstance(memory, dict) else {}
    reason_codes = letta.get("reason_codes", []) if isinstance(letta.get("reason_codes", []), list) else []
    if not step["ok"]:
        errors.append("route_task_failed")
    if str(letta.get("sync_status", "")) != "degraded":
        errors.append("letta_not_degraded_on_failure")
    if "integration_degraded/letta_sync_failed" not in reason_codes:
        errors.append("missing_degraded_reason_code")
    if not isinstance(memory.get("retrieved_top_k", []), list):
        errors.append("retrieval_missing_in_fail_open")
    return {"name": "letta_fail_open_checks", "ok": not errors, "details": [step], "errors": errors}


def run_letta_policy_guard_checks(tmp_dir: Path) -> dict[str, Any]:
    publish_in = tmp_dir / "letta_publish_guard_in.json"
    publish_out = tmp_dir / "letta_publish_guard_out.json"
    write_temp_json(
        publish_in,
        {
            "run_id": "letta-guard-smoke",
            "agent_id": "agent-smoke",
            "project_id": "proj-a",
            "validator_passed": False,
            "governor_approved": False,
            "draft_queue_ref": str(tmp_dir / "missing.json"),
        },
    )
    step = run_cmd([sys.executable, str(PUBLISH_LETTA_DRAFTS), "--input", str(publish_in), "--output", str(publish_out)])
    payload = read_json(publish_out) if publish_out.exists() else {}
    reason_codes = payload.get("reason_codes", []) if isinstance(payload.get("reason_codes", []), list) else []
    errors: list[str] = []
    if step["exit_code"] == 0:
        errors.append("publish_guard_should_fail")
    if "validation_failed/letta_publish_without_gate" not in reason_codes:
        errors.append("missing_publish_gate_reason")
    if "policy_violation/letta_publish_without_governor" not in reason_codes:
        errors.append("missing_governor_reason")
    return {"name": "letta_policy_guard_checks", "ok": not errors, "details": [{**step, "expected_failure": True}], "errors": errors}


def run_experience_packet_checks(tmp_dir: Path) -> dict[str, Any]:
    in_path = tmp_dir / "experience_input.json"
    out_path = tmp_dir / "experience_output.json"
    write_temp_json(
        in_path,
        {
            "run_id": "exp-smoke",
            "task_signature": "memory-reflection",
            "skills_used": ["project-run-reporter", "scratchpad-governor"],
            "gate_failures": [],
            "key_decisions": ["write durable memory"],
            "evidence_pointers": ["/tmp/reporting/episode_summary.json"],
            "final_outcome": "success",
            "trajectory_ref": "/tmp/trajectory.jsonl",
        },
    )
    step = run_cmd(
        [
            sys.executable,
            str(EMIT_EXPERIENCE_PACKET),
            "--input",
            str(in_path),
            "--output",
            str(out_path),
        ]
    )
    errors: list[str] = []
    if step["ok"]:
        payload = read_json(out_path)
        exp = payload.get("experience_packet", {})
        for key in ("task_signature", "skills_used", "gate_failures", "key_decisions", "evidence_pointers", "final_outcome"):
            if key not in exp:
                errors.append(f"missing_experience_field.{key}")
    else:
        errors.append("emit_experience_packet_failed")
    return {"name": "experience_packet_checks", "ok": step["ok"] and not errors, "details": [step], "errors": errors}


def run_runtime_emitter_contract_checks(tmp_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    details: list[dict[str, Any]] = []

    edit_in = tmp_dir / "edit_trace_in.json"
    edit_out = tmp_dir / "edit_trace_out.json"
    write_temp_json(
        edit_in,
        {
            "pass_index": 1,
            "max_passes": 4,
            "before": "draft-1",
            "after": "draft-2",
            "score_before": 0.41,
            "score_after": 0.62,
            "stop_reason": "converged",
        },
    )
    edit_step = run_cmd([sys.executable, str(EMIT_EDIT_TRACE), "--input", str(edit_in), "--output", str(edit_out)])
    details.append(edit_step)
    if not edit_step["ok"]:
        errors.append("emit_edit_trace_failed")
    elif edit_out.exists():
        edit_payload = read_json(edit_out)
        trace = edit_payload.get("edit_trace", {})
        for key in ("pass_index", "before_hash", "after_hash", "validator_delta", "stop_reason"):
            if key not in trace:
                errors.append(f"missing_edit_trace_field.{key}")
    else:
        errors.append("emit_edit_trace_output_missing")

    route_in = tmp_dir / "routing_packet_in.json"
    route_out = tmp_dir / "routing_packet_out.json"
    write_temp_json(
        route_in,
        {
            "step_id": "step-5",
            "candidate_models": ["small-local", "large-remote"],
            "chosen_model": "large-remote",
            "confidence": 0.79,
            "budget_state": {"remaining_tokens": 4000, "remaining_time_ms": 50000},
            "justification_code": "validator_risk_high",
        },
    )
    route_step = run_cmd(
        [sys.executable, str(EMIT_ROUTING_DECISION_PACKET), "--input", str(route_in), "--output", str(route_out)]
    )
    details.append(route_step)
    if not route_step["ok"]:
        errors.append("emit_routing_decision_packet_failed")
    elif route_out.exists():
        route_payload = read_json(route_out)
        packet = route_payload.get("routing_decision_packet", {})
        for key in ("step_id", "candidate_models", "chosen_model", "confidence", "budget_state", "justification_code"):
            if key not in packet:
                errors.append(f"missing_routing_decision_packet_field.{key}")
    else:
        errors.append("emit_routing_decision_packet_output_missing")

    memory_in = tmp_dir / "memory_candidate_in.json"
    memory_out = tmp_dir / "memory_candidate_out.json"
    write_temp_json(
        memory_in,
        {
            "source_run_id": "run-501",
            "eval_task_ids": ["A01", "A03"],
            "artefact_refs": ["/tmp/eval/a03.json"],
            "interface_compliant": True,
            "forbidden_io_detected": False,
            "score": 0.73,
        },
    )
    memory_step = run_cmd(
        [sys.executable, str(EMIT_MEMORY_DESIGN_CANDIDATE), "--input", str(memory_in), "--output", str(memory_out)]
    )
    details.append(memory_step)
    if not memory_step["ok"]:
        errors.append("emit_memory_design_candidate_failed")
    elif memory_out.exists():
        memory_payload = read_json(memory_out)
        packet = memory_payload.get("memory_design_candidate", {})
        for key in ("source_run_id", "eval_task_ids", "artefact_refs", "interface_compliant"):
            if key not in packet:
                errors.append(f"missing_memory_design_candidate_field.{key}")
    else:
        errors.append("emit_memory_design_candidate_output_missing")

    debate_in = tmp_dir / "debate_trace_in.json"
    debate_out = tmp_dir / "debate_trace_out.json"
    write_temp_json(
        debate_in,
        {
            "speaker_role": "reviewer",
            "claim_id": "claim-11",
            "counterclaim_id": "counter-11a",
            "evidence_refs": ["/tmp/evidence/claim-11.json"],
        },
    )
    debate_step = run_cmd([sys.executable, str(EMIT_DEBATE_TRACE), "--input", str(debate_in), "--output", str(debate_out)])
    details.append(debate_step)
    if not debate_step["ok"]:
        errors.append("emit_debate_trace_failed")
    elif debate_out.exists():
        debate_payload = read_json(debate_out)
        trace = debate_payload.get("debate_trace", {})
        for key in ("speaker_role", "timestamp", "claim_id", "counterclaim_id", "evidence_refs"):
            if key not in trace:
                errors.append(f"missing_debate_trace_field.{key}")
    else:
        errors.append("emit_debate_trace_output_missing")

    return {"name": "runtime_emitter_contract_checks", "ok": not errors, "details": details, "errors": errors}


def run_json_render_smoke_checks(tmp_dir: Path) -> dict[str, Any]:
    rendered_out = tmp_dir / "json_render_smoke.html"
    pass_step = run_cmd(
        [
            sys.executable,
            str(JSON_RENDER_SMOKE),
            "--pass-fixture",
            str(HARNESS_PASS_ROUTING_FIXTURE),
            "--fail-fixture",
            str(HARNESS_FAIL_ROUTING_FIXTURE),
            "--rendered-output",
            str(rendered_out),
        ]
    )

    # Expected failure lane to assert fail-closed reason code.
    fail_rendered = tmp_dir / "json_render_smoke_bad.html"
    fail_step = run_cmd(
        [
            sys.executable,
            str(JSON_RENDER_SMOKE),
            "--pass-fixture",
            str(HARNESS_FAIL_ROUTING_FIXTURE),
            "--fail-fixture",
            str(HARNESS_FAIL_ROUTING_FIXTURE),
            "--rendered-output",
            str(fail_rendered),
        ]
    )

    errors: list[str] = []
    if not pass_step["ok"]:
        errors.append("json_render_smoke_pass_lane_failed")
    if not rendered_out.exists():
        errors.append("json_render_smoke_rendered_output_missing")

    try:
        fail_payload = json.loads(fail_step.get("stdout", "") or "{}")
    except json.JSONDecodeError:
        fail_payload = {}
    fail_reason_codes = fail_payload.get("reason_codes", []) if isinstance(fail_payload.get("reason_codes", []), list) else []
    if fail_step["exit_code"] == 0:
        errors.append("json_render_smoke_fail_lane_unexpected_success")
    if "validation_failed/json_render_input_invalid" not in fail_reason_codes:
        errors.append("json_render_smoke_missing_fail_closed_reason")

    return {
        "name": "json_render_smoke_checks",
        "ok": not errors,
        "details": [pass_step, {**fail_step, "expected_failure": True}],
        "errors": errors,
    }


def run_docs_generation_check() -> dict[str, Any]:
    generate = run_cmd(
        [
            sys.executable,
            str(GENERATE_SKILL_DOCS),
            "--skills-root",
            str(CODEX_ROOT),
            "--docs-root",
            str(DOCS_ROOT),
            "--mode",
            "full",
        ]
    )
    return {
        "name": "docs_generation_check",
        "ok": generate["ok"],
        "details": [{**generate, "expected": "generate_docs"}],
        "docs_root": str(DOCS_ROOT),
    }


def run_docs_drift_check(strict_skill_result: bool = False) -> dict[str, Any]:
    validate = run_cmd(
        [
            sys.executable,
            str(VALIDATE_SKILL_DOCS),
            "--skills-root",
            str(CODEX_ROOT),
            "--docs-root",
            str(DOCS_ROOT),
        ]
        + (["--strict"] if strict_skill_result else [])
    )
    validate_payload: dict[str, Any] = {}
    if validate.get("stdout"):
        try:
            validate_payload = json.loads(validate["stdout"])
        except json.JSONDecodeError:
            validate_payload = {}
    mode = "strict" if strict_skill_result else "compat"
    details = [{**validate, "expected": "validate_docs", "mode": mode}]
    if mode == "compat":
        # Compatibility phase: warnings are allowed, hard failures are not.
        ok = bool(validate_payload.get("ok", validate["ok"]))
    else:
        ok = validate["ok"] and bool(validate_payload.get("ok", False))
    return {
        "name": "docs_drift_check",
        "ok": ok,
        "details": details,
        "mode": mode,
        "docs_root": str(DOCS_ROOT),
        "validation": validate_payload,
    }


def run_relation_graph_checks() -> dict[str, Any]:
    graph_path = CODEX_ROOT / "relations/skill_graph.json"
    schema_path = CODEX_ROOT / "relations/skill_graph.schema.json"
    if not graph_path.exists() or not schema_path.exists():
        return {"name": "relation_graph_checks", "ok": False, "details": [{"error": "missing relation graph/schema"}]}
    graph = read_json(graph_path)
    schema = read_json(schema_path)
    errors: list[str] = []
    if not isinstance(graph, dict):
        errors.append("graph_not_object")
    required_root = schema.get("required", [])
    if isinstance(required_root, list):
        errors.extend([f"missing_root.{key}" for key in required_root if key not in graph])
    skills = graph.get("skills", [])
    edges = graph.get("edges", [])
    if not isinstance(skills, list):
        errors.append("skills_not_list")
        skills = []
    if not isinstance(edges, list):
        errors.append("edges_not_list")
        edges = []
    installed = {p.name for p in CODEX_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").exists()}
    for skill in skills:
        if not isinstance(skill, str) or skill not in installed:
            errors.append(f"unknown_skill.{skill}")
    edge_required = ["from", "to", "relation_type", "weight", "source", "updated_at", "applies_after_rl"]
    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"edge_not_object.{idx}")
            continue
        for key in edge_required:
            if key not in edge:
                errors.append(f"edge_missing.{idx}.{key}")
        if edge.get("from") not in installed or edge.get("to") not in installed:
            errors.append(f"edge_unknown_skill.{idx}")
    return {
        "name": "relation_graph_checks",
        "ok": not errors,
        "details": [{"graph_path": str(graph_path), "schema_path": str(schema_path)}],
        "errors": errors,
    }


def run_secret_scan_checks() -> dict[str, Any]:
    scan = run_cmd([sys.executable, str(SECRET_SCAN), "--root", str(CODEX_ROOT), "--mode", "tracked"])
    payload: dict[str, Any] = {}
    if scan.get("stdout"):
        try:
            payload = json.loads(scan["stdout"])
        except json.JSONDecodeError:
            payload = {}
    return {
        "name": "secret_scan_checks",
        "ok": scan["ok"] and bool(payload.get("ok", False)),
        "details": [scan],
        "finding_count": int(payload.get("finding_count", 0) or 0),
        "reason_codes": payload.get("reason_codes", []),
        "findings": payload.get("findings", []),
    }


def run_skill_script_contract_audit(strict_skill_result: bool = False) -> dict[str, Any]:
    python_scripts = sorted(CODEX_ROOT.glob("**/scripts/*.py"))
    missing_skill_result: list[str] = []
    for path in python_scripts:
        text = path.read_text(encoding="utf-8")
        if "skill_result" not in text and "SkillResult" not in text:
            missing_skill_result.append(str(path))
    if strict_skill_result:
        ok = len(missing_skill_result) == 0
    else:
        ok = True
    return {
        "name": "skill_script_contract_audit",
        "ok": ok,
        "missing_skill_result": missing_skill_result[:200],
        "missing_count": len(missing_skill_result),
        "mode": "strict" if strict_skill_result else "compat",
    }


def maybe_record_strict_transition(
    checks: list[dict[str, Any]],
    *,
    strict_skill_result: bool,
) -> dict[str, Any]:
    status = "not_evaluated"
    transition_payload = {
        "strict_transition_applied": False,
        "failure_packet_strict_default": False,
        "evaluated_at_unix": int(time.time()),
        "trigger": "strict_checks_green_and_failure_packet_tests_green",
    }
    if not strict_skill_result:
        status = "strict_flag_not_set"
    else:
        checks_ok = all(item.get("ok") for item in checks)
        fp_gate = any(item.get("name") == "failure_packet_strictness_checks" and item.get("ok") for item in checks)
        if checks_ok and fp_gate:
            transition_payload.update(
                {
                    "strict_transition_applied": True,
                    "failure_packet_strict_default": True,
                    "status": "enabled",
                    "reason": "green_gate",
                }
            )
            STRICT_MODE_STATE_PATH.write_text(json.dumps(transition_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            status = "enabled"
        else:
            transition_payload.update(
                {
                    "status": "compat_fallback",
                    "reason": "gates_not_green",
                }
            )
            status = "compat_fallback"
    return {"name": "strict_mode_transition", "status": status, "state_path": str(STRICT_MODE_STATE_PATH), "payload": transition_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-path",
        default=f"/tmp/skill_system_report_{int(time.time())}.json",
        help="Path for JSON report output",
    )
    parser.add_argument(
        "--strategy-runs-dir",
        default="/tmp/strategy_matrix_runs_latest",
        help="Optional strategy run artefacts directory",
    )
    parser.add_argument(
        "--rebuild-strategy-telemetry",
        action="store_true",
        help="Use deterministic telemetry rebuild before validating strategy runs",
    )
    parser.add_argument(
        "--strict-skill-result",
        action="store_true",
        help="Fail closed for SkillResult envelope checks (Phase 2).",
    )
    parser.add_argument(
        "--sync-mirrors",
        action="store_true",
        help="Also sync .codex skills into mirror roots before checks.",
    )
    args = parser.parse_args()

    started = time.time()
    with tempfile.TemporaryDirectory(prefix="skill-checks-") as tmp:
        tmp_dir = Path(tmp)
        checks = [
            audit_parity(),
            sync_and_verify_three_roots() if args.sync_mirrors else skip_sync_notice(),
            run_typed_validator_checks(tmp_dir),
            run_failure_packet_strictness_checks(tmp_dir),
            run_skillresult_and_reward_checks(tmp_dir, strict_skill_result=args.strict_skill_result),
            run_checklist_contract_checks(tmp_dir),
            run_checklist_timeline_checks(tmp_dir),
            run_crw_authoritative_input_tests(tmp_dir),
            run_distiller_proposal_schema_tests(tmp_dir),
            run_anti_loop_behaviour_tests(tmp_dir),
            run_ctx_namespace_compliance_checks(tmp_dir),
            run_context_repo_contract_checks(tmp_dir),
            run_memory_migration_checks(tmp_dir),
            run_memory_worktree_enforcement_checks(tmp_dir),
            run_memory_defrag_safety_checks(tmp_dir),
            run_retrieval_budget_compliance_checks(tmp_dir),
            run_experience_packet_checks(tmp_dir),
            run_runtime_emitter_contract_checks(tmp_dir),
            run_json_render_smoke_checks(tmp_dir),
            run_simulated_lane_contract_checks(tmp_dir),
            run_snapshot_index_checks(tmp_dir),
            run_progress_proxy_credit_checks(tmp_dir),
            run_evidence_object_contract_checks(tmp_dir),
            run_output_boundary_limit_checks(tmp_dir),
            run_deterministic_preflight_policy_checks(tmp_dir),
            run_skill_invocation_smoke_checks(tmp_dir),
            run_letta_sync_preflight_checks(tmp_dir),
            run_letta_hybrid_retrieval_checks(tmp_dir),
            run_letta_staged_publish_checks(tmp_dir),
            run_letta_fail_open_checks(tmp_dir),
            run_letta_policy_guard_checks(tmp_dir),
            run_execution_audit_contract_checks(tmp_dir),
            run_self_correction_no_regression_checks(tmp_dir),
            run_letta_pointer_contract_checks(tmp_dir),
            run_docs_generation_check(),
            run_docs_drift_check(strict_skill_result=args.strict_skill_result),
            run_relation_graph_checks(),
            run_secret_scan_checks(),
            run_skill_script_contract_audit(strict_skill_result=args.strict_skill_result),
            run_skillbank_flow(tmp_dir),
            run_memory_contract_smoke(tmp_dir),
            run_full_research_flow(tmp_dir),
            run_fanout_benchmark(tmp_dir),
            run_runtime_suite(),
            run_strategy_comparison_snapshot(Path(args.strategy_runs_dir), rebuild_telemetry=args.rebuild_strategy_telemetry),
        ]
    strict_transition_event = maybe_record_strict_transition(checks, strict_skill_result=args.strict_skill_result)

    total_ms = round((time.time() - started) * 1000.0, 2)
    passed = sum(1 for c in checks if c.get("ok"))
    report = {
        "status": "ok" if passed == len(checks) else "failed",
        "checks_passed": passed,
        "checks_total": len(checks),
        "total_duration_ms": total_ms,
        "checks": checks,
        "strict_mode_transition": strict_transition_event,
        "generated_at_unix": int(time.time()),
    }
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report_path": str(report_path)}, ensure_ascii=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
