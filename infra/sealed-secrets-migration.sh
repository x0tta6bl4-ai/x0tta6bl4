#!/bin/bash
# Миграция всех K8s Secrets в SealedSecrets
set -e
NAMESPACE=${1:-default}
SECRETS=$(kubectl -n $NAMESPACE get secrets --no-headers | awk '{print $1}')
for SECRET in $SECRETS; do
  kubectl -n $NAMESPACE get secret $SECRET -o yaml > /tmp/$SECRET.yaml
  kubeseal < /tmp/$SECRET.yaml > /tmp/$SECRET-sealed.yaml
  kubectl -n $NAMESPACE delete secret $SECRET
  kubectl -n $NAMESPACE apply -f /tmp/$SECRET-sealed.yaml
  echo "Migrated $SECRET to SealedSecret"
done
echo "Sealed Secrets migration complete."
