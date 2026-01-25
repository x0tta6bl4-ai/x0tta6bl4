#!/usr/bin/env bash
# final-deploy.sh – Horizon 1 final deployment sequence
set -euo pipefail
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
MSG="Horizon1 Final Deploy: dashboard + social + infra validation @ $TS"

echo "--- x0tta6bl4 FINAL DEPLOY SEQUENCE ---"

# 1. Repo sanity check
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ Not inside a git repository" >&2; exit 1; fi
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Repo OK (branch: $BRANCH)"

# 2. Simple secret scan (lightweight heuristic)
echo "Scanning for accidental secrets..."
SECRETS=$(grep -R -I -n -E 'API_KEY|SECRET|TOKEN|BEGIN RSA PRIVATE KEY' . || true)
if [ -n "$SECRETS" ]; then
  echo "⚠️ Potential secret patterns found:"; echo "$SECRETS" | head -20; echo "Review before pushing."; fi

# 3. Python syntax check
echo "Checking Python syntax..."
PY_ERRORS=0
while IFS= read -r -d '' f; do
  if ! python3 -m py_compile "$f" 2>/dev/null; then
    echo "Syntax error in $f"; PY_ERRORS=1; fi
done < <(find . -name '*.py' -print0)
[ $PY_ERRORS -eq 0 ] && echo "Python syntax clean" || echo "⚠️ Python syntax issues detected"

# 4. JSON validation
echo "Validating JSON files..."
while IFS= read -r -d '' jf; do
  python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$jf" || { echo "Invalid JSON: $jf"; exit 1; }
done < <(find . -name '*.json' -print0)

# 5. Optional Kubernetes health check
if command -v kubectl >/dev/null 2>&1; then
  echo "Running health check (namespace mtls-demo)..."
  if [ -f x0tta6bl4-roadmap/scripts/health-check.sh ]; then
    bash x0tta6bl4-roadmap/scripts/health-check.sh mtls-demo || true
  fi
else
  echo "kubectl not found – skipping cluster health"
fi

# 6. Git add & commit
echo "Committing changes..."
git add .
if git diff --cached --quiet; then
  echo "No staged changes – skipping commit"
else
  git commit -m "$MSG" || echo "Commit skipped"
fi

# 7. Push
echo "Pushing to origin $BRANCH..."
git push origin "$BRANCH"

# 8. Pages instructions
cat <<EOF
---
✅ Push complete.
Next Steps (Manual):
1. Open GitHub → Settings → Pages.
2. Ensure Build & Deployment = GitHub Actions.
3. Workflow deploy-dashboard should run automatically.
4. Access URL once action finishes.

Kickoff brief example:
python3 x0tta6bl4-roadmap/scripts/kickoff_brief.py --format markdown --all --outfile kickoff_brief.md
EOF

echo "--- DONE ---"
