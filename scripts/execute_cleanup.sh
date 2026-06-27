#!/usr/bin/env bash
# Repository Cleanup Execution Script
# Removes bloat from Git index WITHOUT deleting local files.
# Read carefully before running. Make a Git bundle backup first.

set -euo pipefail

say() { printf "%s\n" "$*"; }
warn() { printf "\033[33m%s\033[0m\n" "$*"; }
info() { printf "\033[36m%s\033[0m\n" "$*"; }
success() { printf "\033[32m%s\033[0m\n" "$*"; }

# 0) Safety: check backup bundle exists (pattern)
info "Checking for Git bundle backup in /tmp..."
if ! ls /tmp/x0tta6bl4_backup_*.bundle >/dev/null 2>&1; then
  warn "WARNING: No backup bundle found!"
  say  "Create a backup first:"
  say  "  git bundle create /tmp/x0tta6bl4_backup_$(date +%Y%m%d).bundle --all"
  read -r -p "Continue without backup? (yes/no): " confirm
  if [ "${confirm:-no}" != "yes" ]; then
    say "Aborting. Create backup first."
    exit 1
  fi
fi

# Ensure we are in a Git repo
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  warn "Not a Git repository. Abort."
  exit 1
fi

info "🧹 Starting repository cleanup..."

# 1) Virtual environments
info "1️⃣ Removing virtual environments from Git index..."
# Direct common dirs
git rm --cached -r venv .venv venv_* test_venv 2>/dev/null || true
# Known nested dirs
git rm --cached -r x0tta6bl4_paradox_zone/.venv x0tta6bl4_paradox_zone/test_venv 2>/dev/null || true
# Generic: find any dir named like venv/.venv/venv_*
find . -type d \( -name 'venv' -o -name '.venv' -o -name 'venv_*' -o -name 'test_venv' \) -prune -print0 \
  | xargs -0 -I{} bash -lc 'git rm --cached -r "$1" 2>/dev/null || true' _ {}
success "   Virtual environments untracked (if they were tracked)."

# 2) IDE/tool caches
info "2️⃣ Removing IDE/tool caches from Git index..."
for p in \
  .cache/vscode-cpptools \
  .cache/Google \
  .config/Code/User/workspaceStorage \
  .local/share/code-server
do
  git rm --cached -r "$p" 2>/dev/null || true
done
# Deep matches
find . -type d -path '*/.cache/vscode-cpptools*' -prune -print0 \
  | xargs -0 -I{} bash -lc 'git rm --cached -r "$1" 2>/dev/null || true' _ {}
success "   IDE/tool caches untracked (if they were tracked)."

# 3) Personal/media files
info "3️⃣ Removing personal/media files from Git index..."
# Known roots
git rm --cached -r "Загрузки" "Camera" 2>/dev/null || true
# Individual files by extension
find . -type f \( -name '*.mp4' -o -name '*.avi' -o -name '*.mov' \) -print0 \
  | xargs -0 -I{} bash -lc 'git rm --cached "$1" 2>/dev/null || true' _ {}
# Specific log
git rm --cached -f scan.log 2>/dev/null || true
success "   Personal/media files untracked (if they were tracked)."

# 4) Databases
info "4️⃣ Removing databases from Git index..."
find . -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db-shm' -o -name '*.db-wal' -o -name '*.db-journal' \) -print0 \
  | xargs -0 -I{} bash -lc 'git rm --cached "$1" 2>/dev/null || true' _ {}
success "   Databases untracked (if they were tracked)."

# 5) Archives/backups
info "5️⃣ Removing archives/backups from Git index..."
# Specific heavy snapshot glob
git rm --cached -r archive/snapshots/*.tar.gz 2>/dev/null || true
# Generic archive extensions
find . -type f \( -name '*.tar' -o -name '*.tar.gz' -o -name '*.tgz' -o -name '*.zip' -o -name '*.7z' -o -name '*.rar' \) -print0 \
  | xargs -0 -I{} bash -lc 'git rm --cached "$1" 2>/dev/null || true' _ {}
success "   Archives untracked (if they were tracked)."

# 6) TIFF print files
info "6️⃣ Removing TIFF files from Git index..."
# Known folder
git rm --cached -r "15.09/печать" 2>/dev/null || true
# All TIFFs
find . -type f \( -name '*.tif' -o -name '*.tiff' \) -print0 \
  | xargs -0 -I{} bash -lc 'git rm --cached "$1" 2>/dev/null || true' _ {}
success "   TIFF files untracked (if they were tracked)."

say ""
success "✅ Cleanup complete (index-only)."

say "\n📊 Git status summary (first 40 lines):"
# status might be long; show a preview
(git status --short | head -40) || true

say "\nNext steps:"
say "1) Review changes: git status"
say "2) Move databases: mkdir -p ~/.local/share/x0tta6bl4/databases && find . -type f \\\n   \( -name '*.db' -o -name '*.sqlite*' \) -print0 | xargs -0 -I{} bash -lc 'mv -n "$1" "$HOME/.local/share/x0tta6bl4/databases/" _ {}'"
say "3) Move archives: mkdir -p external_artifacts/relocated && mv archive/snapshots/*.tar.gz external_artifacts/relocated/ 2>/dev/null || true"
say "4) Commit changes: git commit -m 'chore: repository cleanup - remove bloat from tracking'"
say "5) Run Git GC: git gc --aggressive --prune=now"
