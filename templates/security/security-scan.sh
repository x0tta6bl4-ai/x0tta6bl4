#!/usr/bin/env bash
set -eo pipefail

RUN_SNYK=false; RUN_TRIVY=false
SEVERITY="HIGH"; OUTPUT="security-report.html"
IMAGE_TAG="${IMAGE_TAG:-my-image:latest}"

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
  trivy-html-report --input-json "$WORKDIR/trivy-report.json" --output-html "$WORKDIR/trivy-report.html"
fi

{
  echo "<html><body>"
  [ -f "$WORKDIR/snyk-report.html" ] && sed -n '/<body>/,/<\/body>/p' "$WORKDIR/snyk-report.html"
  [ -f "$WORKDIR/trivy-report.html" ] && sed -n '/<body>/,/<\/body>/p' "$WORKDIR/trivy-report.html"
  echo "</body></html>"
} > "$WORKDIR/$OUTPUT"

echo "Report: $WORKDIR/$OUTPUT"
