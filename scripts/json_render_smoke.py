#!/usr/bin/env python3
"""Deterministic json-render smoke check with schema-authoritative validation."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_validate_contracts(script_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("validate_contracts", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load validate_contracts module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_html(payload: dict[str, Any], output_path: Path) -> None:
    escaped = json.dumps(payload, indent=2, ensure_ascii=True)
    html = "".join(
        [
            "<!doctype html><html><head><meta charset=\"utf-8\"><title>json-render smoke</title></head><body>",
            "<h1>json-render smoke output</h1><pre>",
            escaped,
            "</pre></body></html>",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pass-fixture", required=True, type=Path)
    parser.add_argument("--fail-fixture", required=True, type=Path)
    parser.add_argument("--rendered-output", required=True, type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    validate_contracts = _load_validate_contracts(root / "scripts/validate_contracts.py")
    registry = validate_contracts.load_json(root / "harness/skills/registry.json")
    limits = registry.get("policies", {}).get("output_boundaries", {})

    pass_fixture = validate_contracts.load_json(args.pass_fixture)
    fail_fixture = validate_contracts.load_json(args.fail_fixture)

    pass_errors = validate_contracts.validate_contract(
        str(pass_fixture.get("contract", "")),
        pass_fixture.get("payload"),
        limits,
    )
    fail_errors = validate_contracts.validate_contract(
        str(fail_fixture.get("contract", "")),
        fail_fixture.get("payload"),
        limits,
    )

    reason_codes: list[str] = []
    ok = True
    if pass_errors:
        ok = False
        reason_codes.append("validation_failed/json_render_input_invalid")
    if not fail_errors:
        ok = False
        reason_codes.append("validation_failed/json_render_input_invalid")

    if ok:
        _render_html(pass_fixture.get("payload", {}), args.rendered_output)

    result = {
        "ok": ok,
        "pass_fixture": str(args.pass_fixture),
        "fail_fixture": str(args.fail_fixture),
        "rendered_output": str(args.rendered_output),
        "pass_errors": pass_errors,
        "fail_errors": fail_errors,
        "reason_codes": reason_codes,
        "skill_result": {
            "ok": ok,
            "outputs": {
                "rendered_output": str(args.rendered_output),
                "pass_fixture": str(args.pass_fixture),
                "fail_fixture": str(args.fail_fixture),
            },
            "tool_calls": [{"tool_name": "json_render_smoke", "params_hash": "smoke", "duration_ms": 0.0}],
            "cost_units": {"time_ms": 0.0, "tokens": 0, "cost_estimate": 0.0, "risk_class": "low"},
            "artefact_delta": {
                "files_changed": [str(args.rendered_output)] if ok else [],
                "files_created": [str(args.rendered_output)] if ok else [],
                "tests_run": [],
                "urls_fetched": [],
                "screenshots": [],
            },
            "progress_proxy": {"pass_error_count": len(pass_errors), "fail_error_count": len(fail_errors)},
            "failure_codes": reason_codes,
            "suggested_next": [] if ok else ["repair_json_render_input_schema"],
        },
    }
    print(json.dumps(result, ensure_ascii=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
