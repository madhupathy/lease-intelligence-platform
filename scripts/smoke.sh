#!/usr/bin/env bash
# Smoke-test a deployed Lease Intelligence API (gateway or extraction public URL).
# Usage: scripts/smoke.sh <base_url>
# Example: scripts/smoke.sh https://gateway-production-xxxx.up.railway.app
# Env (optional): DEMO_USER, DEMO_PASSWORD, SMOKE_QA_QUESTION
set -euo pipefail

if [[ $# -lt 1 ]] || [[ -z "${1:-}" ]]; then
  echo "usage: $0 <base_url>" >&2
  exit 2
fi

BASE_URL="${1%/}"
DEMO_USER="${DEMO_USER:-demo}"
DEMO_PASSWORD="${DEMO_PASSWORD:-demo}"
SMOKE_QA_QUESTION="${SMOKE_QA_QUESTION:-What is the base rent?}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 2
  }
}

need_cmd curl
need_cmd python

echo "==> health ${BASE_URL}/api/health"
curl -fsS "${BASE_URL}/api/health" >/dev/null

echo "==> login as ${DEMO_USER}"
LOGIN_JSON="$(curl -fsS -X POST "${BASE_URL}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${DEMO_USER}\",\"password\":\"${DEMO_PASSWORD}\"}")"

TOKEN="$(
  DEMO_USER="${DEMO_USER}" DEMO_PASSWORD="${DEMO_PASSWORD}" LOGIN_JSON="${LOGIN_JSON}" python - <<'PY'
import json, os, sys
payload = json.loads(os.environ["LOGIN_JSON"])
token = payload.get("access_token")
if not token:
    print("login response missing access_token", file=sys.stderr)
    sys.exit(1)
print(token)
PY
)"

AUTH_HEADER="Authorization: Bearer ${TOKEN}"

echo "==> list leases"
LEASES_JSON="$(curl -fsS "${BASE_URL}/api/leases" -H "${AUTH_HEADER}")"

LEASE_ID="$(
  LEASES_JSON="${LEASES_JSON}" python - <<'PY'
import json, os, sys
leases = json.loads(os.environ["LEASES_JSON"])
if not isinstance(leases, list) or not leases:
    print("expected non-empty lease list", file=sys.stderr)
    sys.exit(1)
lease_id = leases[0].get("id")
if not lease_id:
    print("first lease missing id", file=sys.stderr)
    sys.exit(1)
print(lease_id)
PY
)"

echo "==> lease detail ${LEASE_ID}"
curl -fsS "${BASE_URL}/api/leases/${LEASE_ID}" -H "${AUTH_HEADER}" >/dev/null

echo "==> QA ${LEASE_ID}"
QA_PAYLOAD="$(
  SMOKE_QA_QUESTION="${SMOKE_QA_QUESTION}" python - <<'PY'
import json, os
print(json.dumps({"question": os.environ["SMOKE_QA_QUESTION"]}))
PY
)"
QA_JSON="$(curl -fsS -X POST "${BASE_URL}/api/leases/${LEASE_ID}/qa" \
  -H "${AUTH_HEADER}" \
  -H 'Content-Type: application/json' \
  -d "${QA_PAYLOAD}")"

QA_JSON="${QA_JSON}" python - <<'PY'
import json, os, sys
payload = json.loads(os.environ["QA_JSON"])
answer = payload.get("answer")
if not isinstance(answer, str) or not answer.strip():
    print("QA response missing answer", file=sys.stderr)
    sys.exit(1)
print("answer:", answer[:200])
PY

echo "OK smoke passed against ${BASE_URL}"
