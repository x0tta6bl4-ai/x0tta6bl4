#!/bin/bash
# x0tta6bl4 VPS Sync Tool
REMOTE="root@89.125.1.107"
DEST="/opt/x0tta6bl4-remote"

echo ">>> Syncing marketing materials to VPS..."
ssh $REMOTE "mkdir -p $DEST"
rsync -avz --exclude=".git" --exclude="node_modules" --exclude="venv" --exclude="recovered_photos" . $REMOTE:$DEST/
echo ">>> Done. Files available on VPS in $DEST"
