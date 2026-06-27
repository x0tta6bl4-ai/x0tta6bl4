#!/usr/bin/env bash
set -eo pipefail

RUN_SNYK=false; RUN_TRIVY=false
SEVERITY="HIGH"; OUTPUT="security-report.html"
IMAGE_TAG="${IMAGE_TAG:-my-image:latest}"

render_json_summary_html() {
  local input_json=$1
  local output_html=$2
  python3 - "$input_json" "$output_html" <<'PY'
import html
import json
import sys
from pathlib import Path

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
try:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
except Exception as exc:
    payload = {"error": str(exc), "Results": []}

rows = []
for result in payload.get("Results", []) if isinstance(payload, dict) else []:
    target = html.escape(str(result.get("Target", "unknown")))
    vulns = result.get("Vulnerabilities") or []
    counts = {}
    if isinstance(vulns, list):
        for vuln in vulns:
            if isinstance(vuln, dict):
                sev = str(vuln.get("Severity") or "UNKNOWN").upper()
                counts[sev] = counts.get(sev, 0) + 1
    summary = ", ".join(f"{html.escape(k)}={v}" for k, v in sorted(counts.items())) or "none"
    rows.append(f"<tr><td>{target}</td><td>{summary}</td></tr>")

if not rows:
    rows.append("<tr><td>scan</td><td>no vulnerabilities reported or unsupported JSON shape</td></tr>")

output_path.write_text(
    "<html><body><h1>Security Scan Summary</h1>"
    "<table><thead><tr><th>Target</th><th>Findings</th></tr></thead>"
    f"<tbody>{''.join(rows)}</tbody></table></body></html>\n",
    encoding="utf-8",
)
PY
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --snyk)      RUN_SNYK=true; shift ;;
    --trivy)     RUN_TRIVY=true; shift ;;
    --severity)  SEVERITY=$2; shift 2 ;;
    --image)     IMAGE_TAG=$2; shift 2 ;;
    --output)    OUTPUT=$2; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

WORKDIR=$(pwd)/scan-results
mkdir -p "$WORKDIR"

if [ "$RUN_SNYK" = true ]; then
  echo "Running Snyk..."
  snyk test --json > "$WORKDIR/snyk-report.json"
  snyk-to-html -i "$WORKDIR/snyk-report.json" -o "$WORKDIR/snyk-report.html"
fi

if [ "$RUN_TRIVY" = true ]; then
  echo "Running Trivy..."
  trivy image \
    --ignore-unfixed \
    --severity "$SEVERITY" \
    --format json \
    -o "$WORKDIR/trivy-report.json" "$IMAGE_TAG"
  if command -v trivy-html-report >/dev/null 2>&1; then
    trivy-html-report --input-json "$WORKDIR/trivy-report.json" --output-html "$WORKDIR/trivy-report.html"
  else
    render_json_summary_html "$WORKDIR/trivy-report.json" "$WORKDIR/trivy-report.html"
  fi
fi

{
  echo "<html><body>"
  [ -f "$WORKDIR/snyk-report.html" ] && sed -n '/<body>/,/<\/body>/p' "$WORKDIR/snyk-report.html"
  [ -f "$WORKDIR/trivy-report.html" ] && sed -n '/<body>/,/<\/body>/p' "$WORKDIR/trivy-report.html"
  echo "</body></html>"
} > "$WORKDIR/$OUTPUT"

echo "Report: $WORKDIR/$OUTPUT"
