#!/bin/bash
# Verify service-to-service encryption in Istio
NAMESPACE=istio-system
POD_A=$(kubectl -n $NAMESPACE get pods -l app=a -o jsonpath='{.items[0].metadata.name}')
POD_B=$(kubectl -n $NAMESPACE get pods -l app=b -o jsonpath='{.items[0].metadata.name}')

kubectl -n $NAMESPACE exec $POD_A -- sh -c "tcpdump -i any port 8080 -c 10"
# Should see encrypted traffic only (no plaintext)
echo "Encryption verification complete."
