# Secondary Exit Requirements

generated_at: `2026-05-28T02:35:33.213260+00:00`

## Status

```text
status=requirements_ready_no_candidate
requirement_count=8
candidate_configured=false
secondary_probe_status=planning_template
manual_failover_readiness_status=blocked_no_incident_trigger
manual_switch_allowed=false
missing_items=NET-01
blocked_items=none
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Requirements

| ID | Status | Group | Requirement | Next Step |
|---|---|---|---|---|
| `SEL-01` | `ready_requirement` | `selection` | Use a new provider and region, not NL and not SPB | choose a provider/region/account that is independent from NL and does not reuse SPB |
| `SEL-02` | `ready_requirement` | `selection` | Use a small, boring daily/emergency profile split | document the secondary as an emergency profile only until manual process is tested |
| `SEL-03` | `ready_no_candidates` | `selection` | Score candidate metadata before choosing a secondary | fill secondary-exit-candidates.example.json with public metadata for non-NL/non-SPB candidates |
| `SEC-01` | `ready_requirement` | `security` | Do not store VPN secrets in repo or reports | generate the future probe config from public metadata only |
| `NET-01` | `missing_candidate` | `network` | Expose an independent public TCP health target | configure a non-secret TCP probe target such as the future public 443 endpoint |
| `NET-02` | `ready_requirement` | `network` | Verify exit IP only after manual test-client activation | after secondary exists, enable client_probe only on a test client and compare expected exit IP |
| `OPS-01` | `ready_requirement` | `operations` | Keep failover manual and reversible | write the exact client-side switch and rollback checklist after a real secondary endpoint exists |
| `OPS-02` | `ready_requirement` | `operations` | Use project-local temp space for diagnostic commands | prefix long local diagnostic/test commands with TMPDIR=/mnt/projects/.tmp until root disk is cleaned |

## Evidence

### SEL-01

Acceptance: candidate provider, region, account, and host are documented as non-NL/non-SPB public metadata

- decision=observe
- failure_domain=external_network
- spb_excluded=true

### SEL-02

Acceptance: daily NL profile remains separate from emergency secondary profile; automatic switching stays disabled

- automatic_failover_allowed=false
- manual_switch_allowed=false

### SEL-03

Acceptance: candidate scorer exists and rejects NL, SPB, placeholders, private addresses, and secret-like material

- candidate_score_status=missing_candidates
- candidate_count=0
- viable_count=0
- top_candidate_label=none

### SEC-01

Acceptance: only public endpoint metadata is stored; no raw URI, UUID, private key, or bot token

- config_generator=nl-diagnostics/create_secondary_exit_config.py
- probe=nl-diagnostics/probe_secondary_exit.py

### NET-01

Acceptance: probe_secondary_exit.py can reach at least one configured TCP port without touching NL

- secondary_probe_status=planning_template
- candidate_configured=false
- candidate_label=secondary-placeholder
- candidate_tcp_ports=[443]

### NET-02

Acceptance: client exit probe is disabled until a manual test profile is activated on a client

- client probe uses local SOCKS only after manual activation
- raw profile secrets remain outside reports

### OPS-01

Acceptance: manual approval, rollback path, and return-to-NL verification are documented before any switch

- manual_failover_readiness_status=blocked_no_incident_trigger
- manual_probe_allowed=false
- manual_switch_allowed=false

### OPS-02

Acceptance: commands that need temporary files can run with TMPDIR=/mnt/projects/.tmp while / is full

- local_root_filesystem_full=true
- recommended_tmpdir=/mnt/projects/.tmp

## Allowed Metadata

- label
- provider name
- region
- public host/IP
- public TCP probe ports
- expected exit IP only after manual test-client activation

## Forbidden Material

- raw VPN URI
- UUID
- private key
- bot token
- subscription link
- NL endpoint
- SPB endpoint

No NL or SPB writes were performed by this requirements builder.
