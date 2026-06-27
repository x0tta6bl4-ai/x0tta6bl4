#!/usr/bin/env bash
# Preview-only: prints safe cleanup commands without executing anything.
# Usage: ./scripts/cleanup_preview.sh > cleanup_commands_preview.txt
set -euo pipefail

cat <<'EOF'
# Preview of safe cleanup commands (no execution)
# Review carefully before running any of them manually.

# 1) Remove virtual environments from Git index (keep files locally)
# Note: if any of these are not tracked, Git will ignore them.
git rm --cached -r venv .venv venv_* test_venv || true

# 2) Remove databases from Git index
# Consider moving DB files to ~/.local/share/x0tta6bl4/databases/ before untracking
# Example move:
#   mkdir -p "$HOME/.local/share/x0tta6bl4/databases" && \
#   find . -type f \( -name '*.db' -o -name '*.sqlite*' \) -exec bash -lc 'mv -n "$0" "$HOME/.local/share/x0tta6bl4/databases/"' {} \;
git rm --cached -r **/*.db **/*.sqlite* || true

# 3) Remove archives/backups from Git index (store in MinIO or DVC)
git rm --cached -r **/*.tar **/*.tar.gz **/*.tgz **/*.zip **/*.7z **/*.rar || true

# 4) Remove obvious IDE/tool caches from Git index (if any slipped in)
git rm --cached -r **/.cache/vscode-cpptools **/.config/Code/User/workspaceStorage || true

# 5) Optionally remove heavy transient package caches (pip)
# git rm --cached -r **/.cache/pip || true

# 6) If Git LFS has very large objects, consider LFS prune/migrate (requires care)
# git lfs prune
# git lfs migrate export --include="path/to/pattern"  # advanced, do only after backup

# If you staged too much by accident:
# git restore --staged .

# After confirming, commit with a clear message:
# git commit -m "repo hygiene: untrack venv, db, archives, caches (no file deletion)"
EOF
