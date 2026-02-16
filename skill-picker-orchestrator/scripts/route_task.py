#!/usr/bin/env python3
"""Generate deterministic skill routing decisions with gate constraints."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List

MEMORY_REPO = Path("/Users/ryangichuru/.codex/skills/memory_repo")
MEMORY_TOP_K_DEFAULT = 5
TRIGGER_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "do",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "use",
    "user",
    "when",
    "with",
    "only",
    "asks",
    "asked",
    "task",
    "tasks",
    "explicitly",
    "request",
    "requested",
    "requests",
}


def load_json(path: Path) -> Dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def evaluate_gates(task: Dict, project_root: Path) -> Dict:
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from evaluate_gates import evaluate  # type: ignore

    return evaluate(task, project_root)


def list_installed_skills(skills_root: Path) -> List[str]:
    skills: List[str] = []
    for child in sorted(skills_root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            skills.append(child.name)
    return skills


def scratchpad_has_route_hint(scratchpad: Path, skills: List[str]) -> bool:
    if not scratchpad.exists():
        return False
    text = scratchpad.read_text(encoding="utf-8")
    return any(skill in text for skill in skills)

def _parse_frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    mapping: dict[str, str] = {}
    for raw in parts[1].splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        mapping[key.strip()] = value.strip().strip("\"'")
    return mapping


def _load_letta_adapter():
    scripts_dir = Path("/Users/ryangichuru/.codex/skills/scripts")
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        import letta_adapter  # type: ignore
    except Exception:
        return None
    return letta_adapter


def _task_text(task: Dict) -> str:
    fields = [
        "task_description",
        "task_signature",
        "goal",
        "mode",
        "constraints",
        "prompt",
        "request",
        "user_message",
    ]
    parts = [str(task.get(key, "")) for key in fields if task.get(key) is not None]
    return " ".join(parts).lower()


def _tokenise(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) >= 3}


def _description_tokens(skills_root: Path, skill: str) -> set[str]:
    skill_file = skills_root / skill / "SKILL.md"
    if not skill_file.exists():
        return set()
    meta = _parse_frontmatter(skill_file)
    description = meta.get("description", "")
    tokens = _tokenise(description)
    return {token for token in tokens if token not in TRIGGER_STOPWORDS}


def select_triggered_skills(task: Dict, installed: List[str], skills_root: Path) -> List[Dict[str, str]]:
    text = _task_text(task)
    task_tokens = _tokenise(text)
    matches: List[tuple[int, str, str]] = []

    for skill in installed:
        skill_norm = skill.replace("-", " ")
        if f"${skill}" in text or skill in text or skill_norm in text:
            matches.append((10, skill, f"explicit mention: {skill}"))
            continue

        desc_tokens = _description_tokens(skills_root, skill)
        if not desc_tokens:
            continue
        overlap = sorted(task_tokens.intersection(desc_tokens))
        if len(overlap) >= 3:
            sample = ", ".join(overlap[:3])
            matches.append((len(overlap), skill, f"trigger overlap: {sample}"))

    ranked: List[Dict[str, str]] = []
    seen: set[str] = set()
    for _, skill, reason in sorted(matches, key=lambda item: (-item[0], item[1])):
        if skill in seen:
            continue
        ranked.append({"skill": skill, "reason": reason})
        seen.add(skill)
    return ranked


def build_memory_retrieval(task: Dict) -> dict:
    query_text = " ".join(
        str(task.get(key, ""))
        for key in ("task_description", "task_signature", "goal", "mode", "constraints")
    ).lower()
    query_tokens = set(re.findall(r"[a-z0-9_]+", query_text))
    retrieval_top_k = int(task.get("memory_top_k", MEMORY_TOP_K_DEFAULT))
    retrieval_top_k = max(1, min(20, retrieval_top_k))

    pinned = sorted(str(path) for path in (MEMORY_REPO / "system").glob("*.md"))
    candidates: list[tuple[float, str]] = []
    for scope in ("domain", "tasks", "ops"):
        for path in sorted((MEMORY_REPO / scope).glob("*.md")):
            meta = _parse_frontmatter(path)
            haystack = " ".join([meta.get("title", ""), meta.get("when_to_use", ""), path.stem]).lower()
            words = set(re.findall(r"[a-z0-9_]+", haystack))
            overlap = len(query_tokens.intersection(words))
            if overlap <= 0:
                continue
            score = overlap / max(1, len(words))
            candidates.append((score, str(path)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    local_selected = [path for _, path in candidates[:retrieval_top_k]]

    letta_result = {
        "enabled": False,
        "agent_id": "",
        "sync_status": "skipped",
        "cache_hit": False,
        "items_considered": 0,
        "items_selected": [],
        "reason_codes": [],
    }
    merged_candidates: list[tuple[float, str, str, dict]] = [
        (score, path, "local", {"path": path}) for score, path in candidates
    ]
    letta_adapter = _load_letta_adapter()
    if letta_adapter is not None:
        sync_input = dict(task)
        if "project_root" not in sync_input:
            sync_input["project_root"] = str(task.get("project_root", ""))
        sync = letta_adapter.preflight_sync(sync_input)
        selected_rows = letta_adapter.rank_items(sync, query_tokens, retrieval_top_k)
        letta_refs: list[str] = []
        for row in selected_rows:
            if not isinstance(row, dict):
                continue
            pointer = row.get("pointer", {})
            if not isinstance(pointer, dict):
                continue
            ref = str(pointer.get("source_uri", f"letta://{pointer.get('folder_id', 'default')}/{pointer.get('document_id', '')}"))
            score = float(row.get("score", 0.0)) + 0.25
            merged_candidates.append((score, ref, "letta", pointer))
            letta_refs.append(ref)
        letta_result = {
            "enabled": bool(sync.get("enabled", False)),
            "agent_id": str(sync.get("agent_id", "")),
            "sync_status": str(sync.get("sync_status", "skipped")),
            "cache_hit": bool(sync.get("cache_hit", False)),
            "items_considered": int(sync.get("items_considered", 0)),
            "items_selected": letta_refs[:retrieval_top_k],
            "reason_codes": sync.get("reason_codes", []) if isinstance(sync.get("reason_codes", []), list) else [],
        }

    merged_candidates.sort(key=lambda item: (-item[0], item[2], item[1]))
    selected_rows = merged_candidates[:retrieval_top_k]
    selected = [row[1] for row in selected_rows]
    selected_objects = [{"source": row[2], "ref": row[1], "meta": row[3]} for row in selected_rows]
    return {
        "memory_repo_root": str(MEMORY_REPO),
        "always_load": pinned,
        "retrieved_top_k": selected,
        "retrieved_top_k_objects": selected_objects,
        "local_retrieved_top_k": local_selected,
        "retrieval_top_k": retrieval_top_k,
        "retrieval_budget_policy": {
            "strict_top_k": retrieval_top_k,
            "skip_low_signal": True,
            "max_pinned_files": 25,
        },
        "letta": letta_result,
    }


def choose_subagent_mode(task: Dict) -> str:
    independent_branches = int(task.get("independent_branches", 0))
    if independent_branches <= 0:
        return "none"
    if independent_branches == 1:
        return "layered"
    return "parallel"


def build_deterministic_preflight(task: Dict) -> Dict:
    explicit = str(task.get("deterministic_check_command", "")).strip()
    if explicit:
        return {
            "attempted": True,
            "selected_command": explicit,
            "blocked_reason": None,
            "result": "planned",
        }

    acceptance_tests = task.get("acceptance_tests", [])
    if isinstance(acceptance_tests, list):
        for row in acceptance_tests:
            if isinstance(row, dict):
                command = str(row.get("command", "")).strip()
                if command:
                    return {
                        "attempted": True,
                        "selected_command": command,
                        "blocked_reason": None,
                        "result": "planned",
                    }

    pattern = str(task.get("deterministic_probe_pattern", task.get("repo_scan_pattern", ""))).strip()
    if pattern:
        return {
            "attempted": True,
            "selected_command": f"rg -n --no-heading --max-count 20 '{pattern}' .",
            "blocked_reason": None,
            "result": "planned",
        }

    return {
        "attempted": True,
        "selected_command": None,
        "blocked_reason": "no_safe_deterministic_probe_found",
        "result": "blocked",
    }


def build_route(task: Dict, installed: List[str], gate_eval: Dict, scratchpad: Path, skills_root: Path) -> Dict:
    started = time.time()
    chosen: List[str] = []
    blocked: List[Dict[str, str]] = []
    gates_applied: List[Dict[str, str]] = []
    reason_codes: List[str] = []
    consecutive_no_progress = max(0, int(task.get("consecutive_no_progress", 0)))
    strategy_switch_tag = "none"
    strategy_switch_decision = "none"

    def include(skill: str, reason: str) -> None:
        if skill in installed and skill not in chosen:
            chosen.append(skill)
            gates_applied.append({"skill": skill, "decision": "included", "reason": reason})
        elif skill not in installed:
            blocked.append({"skill": skill, "reason": "skill not installed"})

    def gate_include(skill: str, gate_key: str) -> None:
        state = gate_eval["gate_states"][gate_key]
        if state["allowed"]:
            include(skill, state["reason"])
        else:
            blocked.append({"skill": skill, "reason": state["reason"]})
        gates_applied.append(
            {"skill": skill, "decision": "allowed" if state["allowed"] else "blocked", "reason": state["reason"]}
        )

    # Base minimal stack.
    deterministic_preflight = build_deterministic_preflight(task)
    include("validation-gate-runner", "validation-first default")
    if bool(task.get("long_horizon", False)) or int(task.get("long_horizon_minutes", 0)) >= 45:
        include("long-run-stability-guard", "long-horizon task")
    if consecutive_no_progress >= 2:
        strategy_switch_tag = "stalled_no_progress"
        strategy_switch_decision = "switch_strategy_then_diagnose"
        reason_codes.append("no_progress/no_progress_loop")
        include("self-correction-loop", "forced strategy switch after 2 no-progress steps")
        include("validation-gate-runner", "forced diagnostic pass after no-progress loop")
    if deterministic_preflight["result"] == "blocked":
        reason_codes.append("validation_failed/deterministic_probe_unavailable")

    gate_include("ambiguity-decision-policy", "ambiguity-decision-policy")
    gate_include("cross-repo-pattern-scanner", "cross-repo-pattern-scanner")
    gate_include("deploy-verify-loop", "deploy-verify-loop")
    gate_include("idle-time-opportunistic-maintainer", "idle-time-opportunistic-maintainer")

    gated_skills = {
        "ambiguity-decision-policy",
        "cross-repo-pattern-scanner",
        "deploy-verify-loop",
        "idle-time-opportunistic-maintainer",
    }
    max_triggered_skills = max(1, int(task.get("max_triggered_skills", 3)))
    trigger_matches = select_triggered_skills(task, installed, skills_root)
    explicit_matches = [item for item in trigger_matches if item["reason"].startswith("explicit mention:")]
    inferred_matches = [item for item in trigger_matches if not item["reason"].startswith("explicit mention:")]
    selected_trigger_matches = explicit_matches + inferred_matches[:max_triggered_skills]
    for item in selected_trigger_matches:
        skill = item["skill"]
        reason = item["reason"]
        if skill in gated_skills:
            continue
        include(skill, f"triggered: {reason}")

    # Subagent collaboration is selected only when branches exist.
    subagent_mode = choose_subagent_mode(task)
    if subagent_mode != "none":
        include("subagent-dag-orchestrator", "independent branches detected")

    has_hints = scratchpad_has_route_hint(scratchpad, chosen)
    confidence = 0.65
    if has_hints:
        confidence += 0.10
    if all(item["decision"] != "blocked" for item in gates_applied if item["skill"] in {
        "ambiguity-decision-policy",
        "cross-repo-pattern-scanner",
        "deploy-verify-loop",
        "idle-time-opportunistic-maintainer",
    }):
        confidence += 0.10
    if "validation-gate-runner" in chosen:
        confidence += 0.05
    missing_context = bool(task.get("missing_context", False))
    if missing_context:
        confidence -= 0.10
    confidence = max(0.0, min(1.0, round(confidence, 2)))

    fallback_sequences: List[List[str]] = []
    if confidence < 0.80:
        fallback_sequences.append(
            [skill for skill in ["validation-gate-runner", "long-run-stability-guard"] if skill in installed]
        )
        if subagent_mode != "none" and "subagent-dag-orchestrator" in installed:
            fallback_sequences.append(["validation-gate-runner", "subagent-dag-orchestrator"])

    memory_retrieval = build_memory_retrieval(task)
    letta_reason_codes = memory_retrieval.get("letta", {}).get("reason_codes", [])
    if isinstance(letta_reason_codes, list):
        for code in letta_reason_codes:
            code_text = str(code)
            if code_text and code_text not in reason_codes:
                reason_codes.append(code_text)
    route = {
        "chosen_skills": chosen,
        "ordered_sequence": chosen,
        "fallback_sequences": fallback_sequences,
        "subagent_mode": subagent_mode,
        "confidence": confidence,
        "gates_applied": gates_applied,
        "blocked_skills": blocked,
        "fallback_if_missing": [
            "Use installed nearest-equivalent skill and mark decision as insufficient evidence."
        ],
        "gate_evaluation": {
            "ambiguity_resolved": gate_eval["ambiguity_resolved"],
            "cross_repo_context_present": gate_eval["cross_repo_context_present"],
            "deploy_context_confirmed": gate_eval["deploy_context_confirmed"],
            "idle_allow_list_present": gate_eval["idle_allow_list_present"],
            "evidence_refs": gate_eval["evidence_refs"],
        },
        "reason_codes": reason_codes,
        "strategy_switch_tags": [strategy_switch_tag] if strategy_switch_tag != "none" else [],
        "no_progress_counters": {
            "incoming_consecutive_no_progress": consecutive_no_progress,
            "switch_threshold": 2,
            "strategy_switch_decision": strategy_switch_decision,
        },
        "memory_retrieval": memory_retrieval,
        "deterministic_preflight": deterministic_preflight,
        "routing_policy_flags": {"deterministic_first_default": True},
        "trigger_matches": selected_trigger_matches,
    }
    decision_trace = {
        "candidate_skills_considered": sorted(chosen + [entry["skill"] for entry in blocked]),
        "selection_reason": "smallest valid gated stack",
        "constraints": {
            "missing_context": bool(task.get("missing_context", False)),
            "independent_branches": int(task.get("independent_branches", 0)),
        },
    }
    exploration_flags = {
        "novel_skill_selected": not has_hints,
        "repeated_skill_detected": len(chosen) != len(set(chosen)),
        "confidence_below_threshold": confidence < 0.80,
    }
    route["decision_trace"] = decision_trace
    route["exploration_flags"] = exploration_flags
    route["expected_cost"] = {
        "estimated_steps": len(chosen),
        "estimated_time_ms": max(1.0, round((time.time() - started) * 1000.0, 2)),
        "risk_class": "medium" if "deploy-verify-loop" in chosen else "low",
    }
    route["expected_progress_proxy"] = {
        "gates_allowed": sum(1 for item in gates_applied if item["decision"] == "allowed"),
        "blocked_skills": len(blocked),
    }
    route["skill_result"] = {
        "ok": True,
        "outputs": {
            "route": {k: route[k] for k in ["chosen_skills", "ordered_sequence", "confidence"]},
            "deterministic_preflight": deterministic_preflight,
        },
        "tool_calls": [
            {
                "tool_name": "route_task",
                "params_hash": hashlib.sha256(json.dumps(task, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16],
                "duration_ms": max(1.0, round((time.time() - started) * 1000.0, 2)),
            }
        ],
        "cost_units": {"time_ms": max(1.0, round((time.time() - started) * 1000.0, 2)), "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
        "artefact_delta": {"files_changed": [], "tests_run": [], "urls_fetched": []},
        "progress_proxy": route["expected_progress_proxy"],
        "failure_codes": reason_codes,
        "suggested_next": ["validation-gate-runner"] if not reason_codes else ["validation-gate-runner", "self-correction-loop"],
        "decision_trace": decision_trace,
        "exploration_flags": exploration_flags,
        "expected_cost": route["expected_cost"],
        "expected_progress_proxy": route["expected_progress_proxy"],
        "reason_codes": reason_codes,
        "loop_flags": route["no_progress_counters"],
        "memory_retrieval": memory_retrieval,
        "deterministic_preflight": deterministic_preflight,
    }
    relation_graph_path = Path("/Users/ryangichuru/.codex/skills/relations/skill_graph.json")
    if relation_graph_path.exists():
        relation_graph = json.loads(relation_graph_path.read_text(encoding="utf-8"))
        if isinstance(relation_graph, dict):
            edges = relation_graph.get("edges", [])
            route["relation_graph_path"] = str(relation_graph_path)
            route["relation_updates"] = [
                edge for edge in edges if isinstance(edge, dict) and edge.get("from") in chosen
            ]
    return route


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-json", required=True, type=Path)
    parser.add_argument("--skills-root", required=True, type=Path)
    parser.add_argument("--scratchpad", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    task = load_json(args.task_json)
    task.setdefault("project_root", str(args.project_root))
    installed = list_installed_skills(args.skills_root)

    gate_eval = evaluate_gates(task, args.project_root)

    route = build_route(task, installed, gate_eval, args.scratchpad, args.skills_root)
    text = json.dumps(route, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
