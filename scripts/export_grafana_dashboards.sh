#!/usr/bin/env bash
#
# Exports every dashboard from the running Grafana instance into ./dashboards/,
# so dashboard edits made in the UI can be committed back to this repo.
#
# Requires a Grafana API token (NOT your admin password) in the environment —
# never pass credentials on the command line where they'd end up in shell
# history. Create one under Grafana > Administration > Service accounts.
#
# Usage:
#   GRAFANA_API_TOKEN="glsa_xxx" GRAFANA_URL="http://localhost:3000" \
#     bash scripts/export_grafana_dashboards.sh

set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/dashboards"

if [[ -z "${GRAFANA_API_TOKEN:-}" ]]; then
  echo "Set GRAFANA_API_TOKEN (a Grafana service account token) before running this script." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "==> Listing dashboards at ${GRAFANA_URL}"
uids=$(curl -sf -H "Authorization: Bearer ${GRAFANA_API_TOKEN}" \
  "${GRAFANA_URL}/api/search?type=dash-db" | python3 -c '
import json, sys
for d in json.load(sys.stdin):
    print(d["uid"])
')

if [[ -z "$uids" ]]; then
  echo "No dashboards found." >&2
  exit 0
fi

for uid in $uids; do
  echo "==> Exporting dashboard uid=${uid}"
  curl -sf -H "Authorization: Bearer ${GRAFANA_API_TOKEN}" \
    "${GRAFANA_URL}/api/dashboards/uid/${uid}" \
    | python3 -c '
import json, sys
payload = json.load(sys.stdin)
dash = payload["dashboard"]
# Strip Grafana-instance-specific fields so the exported file is stable across re-imports.
dash.pop("id", None)
dash.pop("version", None)
print(json.dumps(dash, indent=2))
' > "${OUT_DIR}/${uid}.json"
done

echo "==> Done. Review the diff in ${OUT_DIR} before committing."
