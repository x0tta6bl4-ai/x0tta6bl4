#!/bin/bash
# x0tta6bl4 Phase 1: Archive Cleanup Automation
# Usage: bash scripts/phase1_archive_cleanup.sh
set -e

# 1. Create safety tag and backup branch
if ! git tag | grep -q "v-pre-restructure-20251105"; then
  git tag -a v-pre-restructure-20251105 -m "Backup before Phase 1 migration"
fi
if ! git branch | grep -q "backup/main-20251105"; then
  git branch backup/main-20251105
fi

# 2. Create migration branch
if ! git branch | grep -q "phase-1-archive-cleanup"; then
  git checkout -b phase-1-archive-cleanup
else
  git checkout phase-1-archive-cleanup
fi

# 3. Create archive structure
mkdir -p archive/{legacy,artifacts,snapshots}

# 4. Move backup directories
if [ -d "x0tta6bl4_backup_20250913_204248" ]; then
  git mv x0tta6bl4_backup_20250913_204248 archive/legacy/
fi
if [ -d "x0tta6bl4_paradox_zone/x0tta6bl4_previous" ]; then
  git mv x0tta6bl4_paradox_zone/x0tta6bl4_previous archive/legacy/
fi

# 5. Move tar.gz snapshots
for f in *.tar.gz; do
  if [ -f "$f" ]; then
    git mv "$f" archive/snapshots/
  fi
done

# 6. Add and commit changes
if git status --porcelain | grep -q "^M\|^A\|^D"; then
  git add .
  git commit -m "Phase 1: Archive cleanup - moved backups and legacy files to archive/"
  git push origin phase-1-archive-cleanup
else
  echo "No changes to commit. Archive cleanup already performed."
fi

# 7. Show repo size and test clone
echo "\n---\nRepo size after cleanup:"
du -sh .

echo "\nTesting clone to /tmp/test-clone..."
rm -rf /tmp/test-clone
mkdir -p /tmp/test-clone
cd /tmp/test-clone
# Use local clone for speed
git clone "$(dirname $(pwd))/.." .
ls -lh

echo "\nPhase 1 archive cleanup complete."
