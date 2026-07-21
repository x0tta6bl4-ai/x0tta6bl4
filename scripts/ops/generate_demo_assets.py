#!/usr/bin/env python3
"""
x0tta6bl4 Visual Assets & Demo Generator.

Generates SVG architecture cards, Mermaid diagrams, and HTML status assets
for documentation and release visibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT / "docs" / "assets"


def generate_assets() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    print("🎨 Generating visual demo assets...")

    # 1. Generate Mermaid Sequence Diagram for Autonomous Recovery
    mermaid_file = ASSETS_DIR / "autonomous_recovery_flow.mermaid"
    mermaid_content = """sequenceDiagram
    autonumber
    participant NodeA as Mesh Node A
    participant eBPF as eBPF/XDP Hook
    participant MAPEK as MAPE-K Controller
    participant GNN as GraphSAGE Anomaly Detector
    participant NodeB as Mesh Node B

    NodeA->>eBPF: Send Encrypted Packet (PQC ML-KEM)
    eBPF->>eBPF: Filter Packet (6.66 ns decision)
    eBPF->>NodeB: Forward via Primary Transit Link
    Note over NodeB: Simulated Link Drop (Packet Loss = 100%)
    NodeA->>MAPEK: Telemetry Event (Latency Spike > 500ms)
    MAPEK->>GNN: Classify Metric Anomaly
    GNN-->>MAPEK: Anomaly Confirmed (CRITICAL_LINK_DEGRADATION)
    MAPEK->>MAPEK: Compute Alternative Route Policy
    MAPEK->>eBPF: Update eBPF Routing Table & WireGuard Endpoint
    NodeA->>eBPF: Send Traffic over Backup Route
    eBPF->>NodeB: Forward via Secondary Transit Link
    Note over MAPEK: Validation Framework Check: 100% Invariants PASS
"""
    mermaid_file.write_text(mermaid_content, encoding="utf-8")
    print(f"  ✓ Generated: {mermaid_file}")

    # 2. Generate SVG Architecture Topology Card
    svg_file = ASSETS_DIR / "architecture_topology.svg"
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="100%" height="100%">
  <rect width="800" height="400" rx="12" fill="#0f172a"/>
  
  <text x="400" y="40" fill="#38bdf8" font-family="system-ui, sans-serif" font-size="20" font-weight="bold" text-anchor="middle">
    x0tta6bl4 — Autonomous Self-Healing Mesh Architecture
  </text>
  
  <!-- Node A -->
  <rect x="60" y="100" width="200" height="120" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>
  <text x="160" y="130" fill="#f8fafc" font-family="sans-serif" font-size="16" font-weight="bold" text-anchor="middle">Node A (Local / Edge)</text>
  <text x="160" y="160" fill="#94a3b8" font-family="sans-serif" font-size="12" text-anchor="middle">eBPF/XDP Hook Active</text>
  <text x="160" y="180" fill="#94a3b8" font-family="sans-serif" font-size="12" text-anchor="middle">ML-KEM-768 / ML-DSA-65</text>
  
  <!-- MAPE-K Brain -->
  <rect x="300" y="240" width="200" height="120" rx="8" fill="#1e293b" stroke="#4ade80" stroke-width="2"/>
  <text x="400" y="270" fill="#4ade80" font-family="sans-serif" font-size="16" font-weight="bold" text-anchor="middle">MAPE-K Loop</text>
  <text x="400" y="300" fill="#94a3b8" font-family="sans-serif" font-size="12" text-anchor="middle">GraphSAGE GNN Anomaly</text>
  <text x="400" y="320" fill="#94a3b8" font-family="sans-serif" font-size="12" text-anchor="middle">Auto-Reroute Planner</text>
  
  <!-- Node B -->
  <rect x="540" y="100" width="200" height="120" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>
  <text x="640" y="130" fill="#f8fafc" font-family="sans-serif" font-size="16" font-weight="bold" text-anchor="middle">Node B (NL Server)</text>
  <text x="640" y="160" fill="#94a3b8" font-family="sans-serif" font-size="12" text-anchor="middle">SPIRE mTLS Identity</text>
  <text x="640" y="180" fill="#94a3b8" font-family="sans-serif" font-size="12" text-anchor="middle">Ghost Access VLESS</text>

  <!-- Connectors -->
  <line x1="260" y1="160" x2="540" y2="160" stroke="#38bdf8" stroke-width="3" stroke-dasharray="6,6"/>
  <text x="400" y="150" fill="#38bdf8" font-family="sans-serif" font-size="11" text-anchor="middle">Encrypted Mesh Tunnel</text>
  
  <path d="M 160 220 L 160 300 L 300 300" fill="none" stroke="#4ade80" stroke-width="2"/>
  <path d="M 500 300 L 640 300 L 640 220" fill="none" stroke="#4ade80" stroke-width="2"/>
</svg>
"""
    svg_file.write_text(svg_content, encoding="utf-8")
    print(f"  ✓ Generated: {svg_file}")

    print("✅ All demo assets generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(generate_assets())
