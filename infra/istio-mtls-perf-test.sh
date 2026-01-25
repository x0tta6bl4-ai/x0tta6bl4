#!/bin/bash
# Istio mTLS performance impact test
NAMESPACE=istio-system
SERVICE=your-service
ITERATIONS=1000

for i in $(seq 1 $ITERATIONS); do
  curl -s -o /dev/null -w "%{time_total}\n" https://$SERVICE.$NAMESPACE.svc.cluster.local:443 --cacert /etc/certs/root-cert.pem
done | awk '{sum+=$1} END {print "Average mTLS latency:", sum/NR, "seconds"}'
