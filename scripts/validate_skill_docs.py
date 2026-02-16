#!/usr/bin/env python3
"""Validate generated skill docs coverage, integrity, and drift."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REQUIRED_SKILL_DOC_SECTIONS = [
    "## 1. Skill ID and Path",
    "## 2. Purpose",
    "## 3. When to Use",
    "## 4. Inputs Expected",
    "## 5. Outputs Expected",
    "## 6. Failure Modes and Reason-Code Families",
    "## 7. Tooling and Scripts",
    "## 8. Dependencies and Downstream Consumers",
    "## 9. Constraints and Gates",
    "## 10. Reference Pointers",
]
ALLOWED_MANUAL_DOCS = {
    Path("contracts/context_repo.md"),
}
AGENTS_MERMAID_SOURCES = [
    Path("/Users/ryangichuru/.codex/skills/AGENTS.md"),
    Path("/Users/ryangichuru/.codex/AGENTS.md"),
]
ARCHITECTURE_MMD_PATH = Path("/Users/ryangichuru/.codex/skills/Codex Architecture Dependancy.mmd")


def friendly_doc_name(skill_id: str) -> str:
    return skill_id.replace("/", "__") + ".md"



def list_skill_ids(skills_root: Path) -> list[str]:
    skill_ids: list[str] = []
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        if "docs" in skill_md.parts:
            continue
        skill_ids.append(skill_md.parent.relative_to(skills_root).as_posix())
    return skill_ids



def list_doc_skill_files(docs_root: Path) -> list[Path]:
    skills_dir = docs_root / "skills"
    if not skills_dir.exists():
        return []
    return sorted(path for path in skills_dir.glob("*.md") if path.is_file())



def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")



def check_sections(doc_path: Path) -> list[str]:
    text = load_text(doc_path)
    errors: list[str] = []
    cursor = 0
    for section in REQUIRED_SKILL_DOC_SECTIONS:
        idx = text.find(section, cursor)
        if idx == -1:
            errors.append(f"missing_section:{section}")
            continue
        cursor = idx + len(section)
    return errors



def extract_absolute_pointers(text: str) -> list[str]:
    pointers = re.findall(r"`(/Users/ryangichuru/.codex/skills[^`]+)`", text)
    dedup: list[str] = []
    for pointer in pointers:
        if pointer not in dedup:
            dedup.append(pointer)
    return dedup



def check_pointers(doc_path: Path) -> list[str]:
    text = load_text(doc_path)
    errors: list[str] = []
    for pointer in extract_absolute_pointers(text):
        if not Path(pointer).exists():
            errors.append(f"missing_pointer:{pointer}")
    return errors



def check_index_consistency(skills_root: Path, docs_root: Path) -> list[str]:
    errors: list[str] = []
    expected_skill_ids = list_skill_ids(skills_root)
    expected_docs = {friendly_doc_name(skill_id) for skill_id in expected_skill_ids}

    index_path = docs_root / "indices" / "skills_index.md"
    matrix_path = docs_root / "indices" / "skills_matrix.csv"
    if not index_path.exists():
        errors.append(f"missing_index:{index_path}")
    if not matrix_path.exists():
        errors.append(f"missing_matrix:{matrix_path}")

    if index_path.exists():
        index_text = load_text(index_path)
        for skill_id in expected_skill_ids:
            if f"`{skill_id}`" not in index_text:
                errors.append(f"index_missing_skill:{skill_id}")

    if matrix_path.exists():
        with matrix_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            seen: set[str] = set()
            for row in reader:
                skill_id = row.get("skill_id", "")
                seen.add(skill_id)
                expected_doc = str(docs_root / "skills" / friendly_doc_name(skill_id))
                if row.get("doc_path", "") != expected_doc:
                    errors.append(f"matrix_doc_path_mismatch:{skill_id}")
            for skill_id in expected_skill_ids:
                if skill_id not in seen:
                    errors.append(f"matrix_missing_skill:{skill_id}")
            for skill_id in sorted(seen):
                if skill_id not in expected_skill_ids:
                    errors.append(f"matrix_unknown_skill:{skill_id}")

    skill_files = list_doc_skill_files(docs_root)
    seen_doc_names = {path.name for path in skill_files}
    for expected in sorted(expected_docs):
        if expected not in seen_doc_names:
            errors.append(f"missing_skill_doc:{expected}")
    for found in sorted(seen_doc_names):
        if found not in expected_docs:
            errors.append(f"orphan_skill_doc:{found}")
    return errors



def compare_directories(expected_root: Path, actual_root: Path) -> list[str]:
    errors: list[str] = []
    expected_files = sorted(path for path in expected_root.rglob("*") if path.is_file())
    actual_files = sorted(path for path in actual_root.rglob("*") if path.is_file())

    expected_rel = {path.relative_to(expected_root) for path in expected_files}
    actual_rel = {path.relative_to(actual_root) for path in actual_files}

    for rel in sorted(expected_rel - actual_rel):
        errors.append(f"drift_missing_file:{rel.as_posix()}")
    for rel in sorted(actual_rel - expected_rel):
        if rel in ALLOWED_MANUAL_DOCS:
            continue
        if rel.parts and rel.parts[0] == "reviews":
            continue
        errors.append(f"drift_extra_file:{rel.as_posix()}")

    for rel in sorted(expected_rel & actual_rel):
        expected_text = (expected_root / rel).read_text(encoding="utf-8")
        actual_text = (actual_root / rel).read_text(encoding="utf-8")
        if expected_text != actual_text:
            errors.append(f"drift_content_mismatch:{rel.as_posix()}")
    return errors



def run_generation_drift_check(skills_root: Path, docs_root: Path) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="skill-docs-validate-") as tmp:
        tmp_root = Path(tmp) / "docs"
        cmd = [
            sys.executable,
            "/Users/ryangichuru/.codex/skills/scripts/generate_skill_docs.py",
            "--skills-root",
            str(skills_root),
            "--docs-root",
            str(tmp_root),
            "--mode",
            "full",
        ]
        result = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            return ["generator_failed_for_drift_check"]
        return compare_directories(tmp_root, docs_root)


def normalize_mermaid_text(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"


def extract_mermaid_block(markdown: str) -> str | None:
    match = re.search(r"```mermaid\s*\n(.*?)\n```", markdown, flags=re.DOTALL)
    if not match:
        return None
    return match.group(1)


def check_architecture_mermaid_sync() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    source_path = next((path for path in AGENTS_MERMAID_SOURCES if path.exists()), None)
    if source_path is None:
        warnings.append("architecture_mermaid_source_missing")
        return errors, warnings
    if not ARCHITECTURE_MMD_PATH.exists():
        errors.append(f"architecture_mmd_missing:{ARCHITECTURE_MMD_PATH}")
        return errors, warnings

    agents_text = load_text(source_path)
    source_mermaid = extract_mermaid_block(agents_text)
    if source_mermaid is None:
        warnings.append(f"architecture_mermaid_block_missing:{source_path}")
        return errors, warnings

    current_mmd = load_text(ARCHITECTURE_MMD_PATH)
    if normalize_mermaid_text(source_mermaid) != normalize_mermaid_text(current_mmd):
        errors.append(
            "architecture_mermaid_out_of_sync:"
            f"source={source_path};target={ARCHITECTURE_MMD_PATH}"
        )
    return errors, warnings



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", default="/Users/ryangichuru/.codex/skills", type=Path)
    parser.add_argument("--docs-root", default="/Users/ryangichuru/.codex/skills/docs", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    skills = list_skill_ids(args.skills_root)
    doc_files = list_doc_skill_files(args.docs_root)

    section_errors: dict[str, list[str]] = {}
    pointer_errors: dict[str, list[str]] = {}

    for doc_path in doc_files:
        sec = check_sections(doc_path)
        ptr = check_pointers(doc_path)
        if sec:
            section_errors[str(doc_path)] = sec
        if ptr:
            pointer_errors[str(doc_path)] = ptr

    index_errors = check_index_consistency(args.skills_root, args.docs_root)
    drift_errors = run_generation_drift_check(args.skills_root, args.docs_root)
    architecture_errors, architecture_warnings = check_architecture_mermaid_sync()

    errors: list[str] = []
    for doc_path, items in section_errors.items():
        errors.extend([f"{doc_path}:{item}" for item in items])
    for doc_path, items in pointer_errors.items():
        errors.extend([f"{doc_path}:{item}" for item in items])
    errors.extend(index_errors)
    errors.extend(architecture_errors)

    warnings: list[str] = []
    warnings.extend(drift_errors)
    warnings.extend(architecture_warnings)

    if args.strict:
        errors.extend(drift_errors)

    payload = {
        "ok": len(errors) == 0,
        "mode": "strict" if args.strict else "compat",
        "skills_count": len(skills),
        "docs_count": len(doc_files),
        "errors": errors,
        "warnings": warnings,
        "section_error_count": sum(len(v) for v in section_errors.values()),
        "pointer_error_count": sum(len(v) for v in pointer_errors.values()),
        "index_error_count": len(index_errors),
        "drift_error_count": len(drift_errors),
        "architecture_error_count": len(architecture_errors),
        "architecture_warning_count": len(architecture_warnings),
    }
    payload["skill_result"] = {
        "ok": payload["ok"],
        "outputs": {
            "mode": payload["mode"],
            "skills_count": payload["skills_count"],
            "docs_count": payload["docs_count"],
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "tool_calls": [],
        "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
        "artefact_delta": {"files_changed": [], "files_created": [], "tests_run": [], "urls_fetched": [], "screenshots": []},
        "failure_codes": [] if payload["ok"] else ["validation_failed/skill_docs"],
        "progress_proxy": {"errors": len(errors), "warnings": len(warnings)},
        "suggested_next": [] if payload["ok"] else ["regenerate_skill_docs", "fix_drift_or_contract_errors"],
    }

    text = json.dumps(payload, indent=2, ensure_ascii=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["ok"] or (not args.strict and len(errors) == 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
