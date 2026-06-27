#!/bin/bash
# Автоматическая ротация секретов SealedSecrets
set -e
NAMESPACE=${1:-default}
SECRETS=$(kubectl -n $NAMESPACE get sealedsecret --no-headers | awk '{print $1}')
for SECRET in $SECRETS; do
  # Генерация нового значения (пример для jwt)
  NEW_VALUE=$(openssl rand -hex 32)
  kubectl -n $NAMESPACE patch sealedsecret $SECRET --type='json' -p='[{"op": "replace", "path": "/spec/encryptedData/jwt", "value": "'$NEW_VALUE'"}]'
  echo "Rotated secret $SECRET"
done
echo "Secret rotation complete."
