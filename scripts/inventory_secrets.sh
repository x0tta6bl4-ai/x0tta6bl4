#!/usr/bin/env bash
set -euo pipefail

OUTPUT=${1:-secrets_report.md}

echo "# Secrets Inventory Report" > "$OUTPUT"
echo "Generated: $(date -Iseconds)" >> "$OUTPUT"
echo >> "$OUTPUT"

echo "## Potential secret files (*.pem, *.key, *.p12, *.der)" >> "$OUTPUT"
find . \( -name "*.pem" -o -name "*.key" -o -name "*.p12" -o -name "*.der" \) \
  | grep -v ".example" | sed 's#^#- #g' >> "$OUTPUT" || true

echo >> "$OUTPUT"
echo "## .env files tracked by git" >> "$OUTPUT"
git ls-files | grep -E '\\.env$' | sed 's#^#- #g' >> "$OUTPUT" || true

echo >> "$OUTPUT"
echo "## Suggestions" >> "$OUTPUT"
echo "- Migrate secrets to Sealed Secrets / SOPS" >> "$OUTPUT"
echo "- Rotate any discovered keys/certificates" >> "$OUTPUT"
echo "- Add patterns to .gitignore where appropriate" >> "$OUTPUT"

echo "\nReport written to $OUTPUT"
