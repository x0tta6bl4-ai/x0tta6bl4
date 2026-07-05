# SPIRE Telemetry Patch

This directory contains telemetry-enabled configs to expose Prometheus metrics:

- `spire-server-telemetry.conf` -> Prometheus on :9091
- `spire-agent-telemetry.conf` -> Prometheus on :9092

## Integration Plan (Separate PR)
1. Add container ports to SPIRE server/agent deployments:
   - Server: 9091
   - Agent: 9092
2. Mount corresponding config files (replace current config path).
3. Update Prometheus scrape config:
```yaml
  - job_name: 'spire-server'
    static_configs:
      - targets: ['spire-server.spire:9091']
  - job_name: 'spire-agent'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_container_name]
        regex: spire-agent
        action: keep
      - source_labels: [__meta_kubernetes_pod_container_port_number]
        regex: '9092'
        action: keep
```
4. Extend dashboard with actual SPIRE handshake / SVID metrics once they appear.

## Metrics Expected
- `spire_server_svid_expiration_seconds`
- `spire_agent_svid_renew_total`
- `spire_server_registration_entries`
- `go_memstats_*` runtime stats

## Validation
After redeploy:
```bash
kubectl port-forward svc/spire-server -n spire 9091:9091 &
curl -s localhost:9091/metrics | grep spire_server_registration_entries
```
