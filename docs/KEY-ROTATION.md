# Key Rotation

The Go rotation manager in [rotation.go](/mnt/projects/agent/internal/crypto/pqc/rotation.go) uses these defaults:

- ML-KEM-768 rotation every 30 days
- ML-DSA-65 rotation every 90 days
- 7-day overlap where old and new keys are both accepted
- NTRU-HRSS-701 backup references for disaster recovery

## Runtime flow

1. The active generation is advertised in new handshakes through [noise.go](/mnt/projects/agent/internal/crypto/pqc/noise.go).
2. When `RotateDue()` is called after the configured interval, a new generation becomes active.
3. The previous generation is retained until `AcceptUntil`, allowing peers to re-authenticate without downtime.
4. Expired generations are removed from the accepted set after the overlap window ends.

## Kubernetes automation

- Secret material lives in [k8s/secrets-pqc-keys.yaml](/mnt/projects/k8s/secrets-pqc-keys.yaml)
- The daily rotation trigger lives in [k8s/cronjob-key-rotation.yaml](/mnt/projects/k8s/cronjob-key-rotation.yaml)
- The CronJob must run an agent image that exposes a `rotate-keys` command wired to the Go rotation manager

## Disaster recovery

- NTRU backup keys are treated as externally generated recovery artifacts
- Store backup private keys outside the workload namespace whenever possible
- Require dual control to unseal and re-import backup keys
- Log all restore events through the tamper-evident audit sink in [zerotrust.go](/mnt/projects/agent/internal/security/zerotrust.go)
