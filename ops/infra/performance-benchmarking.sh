#!/bin/bash
# Performance benchmarking for mesh, RAG, throughput, MTTR
set -e
# Mesh routing latency
curl -s http://localhost:9091/metrics | grep mesh_routing_latency_ms
# RAG query latency
curl -s http://localhost:9091/metrics | grep rag_query_latency_ms
# Throughput
curl -s http://localhost:9091/metrics | grep mesh_throughput_gbps
# Resource utilization
curl -s http://localhost:9091/metrics | grep -E 'node_cpu_usage|node_memory_usage|node_gpu_usage'
# MTTR (example: parse recovery logs)
grep 'recovery completed' /var/log/mesh-recovery.log | awk '{print $NF}'
echo "Performance benchmarking complete."
