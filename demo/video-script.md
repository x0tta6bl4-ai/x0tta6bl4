# x0tta6bl4 MaaS — 2-Minute Demo Video Script

**Duration:** 2:00 | **Format:** Screen recording + voiceover | **Audience:** Technical buyers, investors

---

## Production Notes

- Screen resolution: 1920×1080
- Record at 60fps, export 1080p60
- Background: dark terminal + Grafana dark theme
- Music: ambient lo-fi (no copyright, fades at :20 and 1:45)

---

## Script

### [0:00–0:12] — Hook (cold open, no music)

**[Screen: Black. Terminal cursor blinks.]**

> **VO:** "What if your network could heal itself faster than a human could notice something was wrong?"

**[Screen: Grafana topology dashboard animates in — 47 green nodes, mesh edges pulsing]**

> **VO:** "This is x0tta6bl4 — a post-quantum mesh network that self-heals in under 2 seconds."

---

### [0:12–0:35] — Live Mesh Topology

**[Screen: React dashboard — TopologyViewer with 47 nodes]**

> **VO:** "Our D3.js topology viewer shows your entire mesh in real time — every node, every edge, every latency measurement."

**[Zoom in on node detail panel]**

> **VO:** "RSSI, SNR, uptime percentage, peer connections — all live, all sub-500 millisecond refresh."

**[Point to status bar]**

> **VO:** "Right now: 47 active nodes, 12 edges, 98.5% uptime. Let's break it."

---

### [0:35–1:00] — Chaos Injection

**[Screen: Terminal. Type command:]**
```bash
kubectl apply -f chaos/node-failure.yaml -n x0tta-production
```

> **VO:** "We're triggering a Litmus chaos experiment — killing 30% of nodes simultaneously."

**[Screen: Topology viewer — 14 nodes turn red. Grafana MTTR gauge starts climbing.]**

> **VO:** "Nodes are going down. Watch the MAPE-K self-healing loop kick in."

**[Screen: Loki log stream — healing events scrolling]**
```
[node-12] anomaly detected: pod_kill — initiating heal sequence
[node-08] heal accepted: strategy=auto eventId=evt-chaos-001
[node-15] batman-adv route recalculated — traffic rerouted
```

> **VO:** "The GraphSAGE GNN detected the anomaly pattern — 94% accuracy — and rerouted traffic automatically."

---

### [1:00–1:22] — Recovery (The Money Shot)

**[Screen: Grafana — MTTR histogram. Bar at 1.8s. Target line at 2.5s.]**

> **VO:** "Recovery complete. 1.8 seconds mean time to recover — our SLA target is 2.5."

**[Screen: Topology viewer — all 47 nodes green again. Animation: nodes fade back to green one by one.]**

> **VO:** "Every node back online. Zero manual intervention."

**[Screen: SLA dashboard — Uptime 98.5%, MTTR 1.8s, Throughput 12.4 Mbps]**

> **VO:** "And throughput never dropped below SLA. The mesh routed around the failure."

---

### [1:22–1:42] — PQC Security

**[Screen: PQC Heatmap component — Kyber handshake latency grid]**

> **VO:** "Every connection is protected by post-quantum cryptography — Kyber-768, FIPS 203 compliant."

**[Zoom on heatmap — all cells green, p95 < 10ms]**

> **VO:** "Kyber handshake p95: under 10 milliseconds. Quantum-safe, production-speed."

**[Screen: Terminal:]**
```bash
cosign verify registry.gitlab.com/x0tta/api-gateway:v1.0.0
# ✓ verified: x0tta6bl4 supply chain attested
```

> **VO:** "Every image is cosign-attested with a full SPDX SBOM. Supply chain secured."

---

### [1:42–2:00] — CTA

**[Screen: Slide over terminal — dark background, text appears:]**

```
x0tta6bl4 MaaS v1.0.0

98.5% Uptime  |  1.8s MTTR  |  12.4 Mbps
94% GNN       |  PQC FIPS 203/204

helm install x0tta oci://registry.gitlab.com/x0tta/charts/x0tta6bl4-commercial
```

> **VO:** "x0tta6bl4 MaaS — production-ready, quantum-safe, self-healing mesh. Deploy in one command."

**[Screen: URL + QR code:]**
```
x0tta6bl4.io  |  enterprise@x0tta6bl4.io
```

> **VO:** "Get your free trial at x0tta6bl4.io."

**[Fade to black. End card: logo + website]**

---

## B-Roll Shots (for editing)

1. Terminal scrolling mesh-node logs (30s loop)
2. Grafana topology dashboard idle state (nodes pulsing, 15s)
3. MTTR gauge animating from 0 to 1.8s (5s)
4. PQC heatmap — all green cells (10s)
5. `kubectl get pods -n x0tta-production` — all Running (5s)

## Captions

Full transcript available. Add subtitles for accessibility (SRT file in `demo/subtitles.srt`).
