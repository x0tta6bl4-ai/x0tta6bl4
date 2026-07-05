#!/bin/bash
# Процедура аварийного восстановления SealedSecrets
set -e
NAMESPACE=${1:-default}
BACKUP_DIR=${2:-/backup/sealedsecrets}
for FILE in $BACKUP_DIR/*.yaml; do
  kubectl -n $NAMESPACE apply -f $FILE
  echo "Restored $FILE"
done
echo "Emergency secret recovery complete."
