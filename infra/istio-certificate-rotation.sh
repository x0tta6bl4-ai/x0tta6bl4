#!/bin/bash
# Istio certificate rotation automation (90-day cycle)
set -e
NAMESPACE=istio-system
SECRET_NAME=istio-ca-secret
NEW_CERT=ca-cert.pem
NEW_KEY=ca-key.pem

# Generate new certs (example, replace with your CA process)
openssl req -x509 -nodes -days 90 -newkey rsa:2048 -keyout $NEW_KEY -out $NEW_CERT -subj "/CN=Istio-CA"

# Update secret in Kubernetes
kubectl -n $NAMESPACE delete secret $SECRET_NAME || true
kubectl -n $NAMESPACE create secret tls $SECRET_NAME --cert=$NEW_CERT --key=$NEW_KEY

# Restart Istio pods to pick up new certs
kubectl -n $NAMESPACE rollout restart deployment istiod

echo "Istio CA certificate rotated successfully."
