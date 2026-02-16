#!/bin/bash

# Create archive directory
ARCHIVE_DIR="docs/archive/root_artifacts_$(date +%Y%m%d)"
mkdir -p "$ARCHIVE_DIR"

# Define critical files to KEEP
# We will move everything else that matches patterns
# Easier to exclude than include in this mess

# Move markdown files (except REDME.md)
for f in *.md; do
    if [[ "$f" != "README.md" && "$f" != "CHANGELOG.md" && "$f" != "CONTRIBUTING.md" && "$f" != "LICENSE" ]]; then
        mv "$f" "$ARCHIVE_DIR/" 2>/dev/null
    fi
done

# Move text files (except criticals if any)
for f in *.txt; do
    if [[ "$f" != "requirements.txt" && "$f" != "requirements-*.txt" && "$f" != "CMakeLists.txt" ]]; then
        mv "$f" "$ARCHIVE_DIR/" 2>/dev/null
    fi
done

# Move specific large JSON dumps (not config)
mv *_report.json "$ARCHIVE_DIR/" 2>/dev/null
mv *_analysis.json "$ARCHIVE_DIR/" 2>/dev/null
mv *_tree.json "$ARCHIVE_DIR/" 2>/dev/null
mv *_dump.json "$ARCHIVE_DIR/" 2>/dev/null

# Move shell scripts that are likely one-off (keeping standard ones)
# This is risky, so maybe just move specific patterns
mv *_check.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_deploy.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_setup.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_start.sh "$ARCHIVE_DIR/" 2>/dev/null
mv *_test.sh "$ARCHIVE_DIR/" 2>/dev/null
mv QUICK_*.sh "$ARCHIVE_DIR/" 2>/dev/null

echo "Root cleanup complete. Archived to $ARCHIVE_DIR"
