#!/bin/bash

# Create archive directory
ARCHIVE_DIR="docs/archive/root_artifacts_$(date +%Y%m%d)"
mkdir -p "$ARCHIVE_DIR"

# Define critical files to KEEP
# We will move everything else that matches patterns
# Easier to exclude than include in this mess

# Define critical files to KEEP (Release Guardrails)
KEEP_LIST=(
    "README.md"
    "CHANGELOG.md"
    "CONTRIBUTING.md"
    "LICENSE"
    "AGENTS.md"
    "RC1_MANIFEST.json"
    "RC1_SIGNOFF.md"
    "RC1_RELEASE_NOTES.md"
    "RC1_STATUS_PAGE.md"
    "requirements.txt"
    "requirements-*.txt"
    "go.mod"
    "go.sum"
    "package.json"
    "pyproject.toml"
)

# Function to check if file is in KEEP_LIST
is_critical() {
    local f=$1
    for critical in "${KEEP_LIST[@]}"; do
        if [[ "$f" == "$critical" ]]; then
            return 0
        fi
    done
    return 1
}

# Move markdown files (except criticals)
for f in *.md; do
    if ! is_critical "$f"; then
        mv "$f" "$ARCHIVE_DIR/" 2>/dev/null
    fi
done

# Move JSON files (except criticals)
for f in *.json; do
    if ! is_critical "$f"; then
        # Extra protection for RC1 patterns
        if [[ "$f" != RC1_* ]]; then
            mv "$f" "$ARCHIVE_DIR/" 2>/dev/null
        fi
    fi
done

# Move shell scripts that are likely one-off (keeping standard ones)
# This is risky, so maybe just move specific patterns
mv *_check.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_deploy.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_setup.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_start.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_test.sh "$ARCHIVE_DIR/" 2>/dev/null
mv QUICK_*.sh "$ARCHIVE_DIR/" 2>/dev/null

echo "Root cleanup complete. Archived to $ARCHIVE_DIR"
