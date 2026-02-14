#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$ROOT/harness/skills/registry.json"
SCHEMA_DIR="$ROOT/harness/skills/schemas"

fail() {
  echo "[FAIL] $1" >&2
  exit 1
}

command -v jq >/dev/null 2>&1 || fail "jq is required"

jq -e . "$REGISTRY" >/dev/null || fail "registry.json is invalid JSON"

for f in skill_request.schema.json skill_result.schema.json evidence_object.schema.json validator_result.schema.json experience_packet.schema.json; do
  jq -e . "$SCHEMA_DIR/$f" >/dev/null || fail "$f is invalid JSON"
done

jq -e '.skills_version and (.skills | type == "array")' "$REGISTRY" >/dev/null || fail "registry missing top-level fields"

jq -e '.skills[] | .name and .type and .inputs_schema and .outputs_schema and (.depends_on|type=="array") and (.triggers|type=="array")' "$REGISTRY" >/dev/null || fail "registry skill entries missing required fields"

echo "[PASS] Repository validation succeeded."
