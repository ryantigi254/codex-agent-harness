#!/usr/bin/env python3
"""Fail-closed scanner for hard-coded secrets in git-tracked or staged files."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

REASON_CODE = "policy_violation/hardcoded_secret_detected"

KEY_PATTERN = r"(?:api[_-]?key|secret(?:_key)?|token|password|passwd|private[_-]?key|client[_-]?secret)"
ASSIGNMENT_RE = re.compile(
    rf"(?i)\b(?P<key>{KEY_PATTERN})\b\s*[:=]\s*[\"'](?P<value>[^\"']{{20,}})[\"']"
)
JSON_RE = re.compile(
    rf"(?i)\"(?P<key>{KEY_PATTERN})\"\s*:\s*\"(?P<value>[^\"]{{20,}})\""
)

HEX_RE = re.compile(r"^[a-fA-F0-9]{32,}$")
BASE64ISH_RE = re.compile(r"^[A-Za-z0-9_\-+/=]{24,}$")

PLACEHOLDER_MARKERS = {
    "example",
    "placeholder",
    "changeme",
    "change_me",
    "your_",
    "dummy",
    "sample",
    "fake",
    "redacted",
    "test",
    "null",
    "none",
}

TEXT_FILE_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".sh",
    ".zsh",
    ".bash",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".java",
    ".rb",
    ".rs",
    ".php",
    ".sql",
    ".xml",
}


def run_git(root: Path, args: list[str]) -> list[str]:
    cmd = ["git", "-C", str(root), *args]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def file_list(root: Path, mode: str) -> list[Path]:
    if mode == "tracked":
        rel_paths = run_git(root, ["ls-files"])
    elif mode == "staged":
        rel_paths = run_git(root, ["diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"])
    else:
        raise ValueError(f"unsupported mode: {mode}")
    files: list[Path] = []
    for rel in rel_paths:
        path = root / rel
        if path.is_file():
            files.append(path)
    return files


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_FILE_SUFFIXES:
        return True
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in chunk


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    frequencies: dict[str, int] = {}
    for char in value:
        frequencies[char] = frequencies.get(char, 0) + 1
    length = len(value)
    entropy = 0.0
    for count in frequencies.values():
        probability = count / length
        entropy -= probability * math.log2(probability)
    return entropy


def looks_placeholder(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith("${") or lowered.startswith("$"):
        return True
    if lowered.startswith("<") and lowered.endswith(">"):
        return True
    if " " in value or "\t" in value:
        return True
    if value.startswith("http://") or value.startswith("https://"):
        return True
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def looks_sensitive(value: str) -> bool:
    if len(value) < 20:
        return False
    if looks_placeholder(value):
        return False
    if HEX_RE.fullmatch(value):
        return True
    if BASE64ISH_RE.fullmatch(value) and shannon_entropy(value) >= 3.4:
        return True
    return shannon_entropy(value) >= 3.8 and any(c.isdigit() for c in value)


def redact(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def scan_file(path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings
    except OSError:
        return findings

    for line_no, line in enumerate(text.splitlines(), start=1):
        for matcher in (ASSIGNMENT_RE, JSON_RE):
            match = matcher.search(line)
            if not match:
                continue
            key_name = match.group("key")
            value = match.group("value").strip()
            if not looks_sensitive(value):
                continue
            findings.append(
                {
                    "file": str(path),
                    "line": line_no,
                    "key": key_name,
                    "value_preview": redact(value),
                    "reason_code": REASON_CODE,
                }
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Git repository root")
    parser.add_argument("--mode", choices=["tracked", "staged"], default="tracked")
    args = parser.parse_args()

    root = args.root.resolve()
    files = file_list(root, args.mode)
    findings: list[dict[str, Any]] = []

    for path in files:
        if not is_text_file(path):
            continue
        findings.extend(scan_file(path))

    payload = {
        "ok": len(findings) == 0,
        "mode": args.mode,
        "scanned_files": len(files),
        "finding_count": len(findings),
        "reason_codes": [REASON_CODE] if findings else [],
        "findings": findings[:100],
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
