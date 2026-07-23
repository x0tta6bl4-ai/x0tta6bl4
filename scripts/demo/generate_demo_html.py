#!/usr/bin/env python3
"""Generate demo screenshots as HTML files for embedding in README.

Creates self-contained HTML files that render terminal output with
syntax highlighting and styling — ready for screenshots or embedding.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT / "docs" / "assets" / "demo"

TERMINAL_CSS = """
<style>
  body { margin: 0; padding: 20px; background: #1e1e1e; font-family: 'Courier New', monospace; }
  .terminal { background: #0d1117; border-radius: 8px; padding: 20px; max-width: 800px; margin: 0 auto; }
  .prompt { color: #7ee787; }
  .output { color: #c9d1d9; }
  .success { color: #3fb950; }
  .header { color: #58a6ff; font-weight: bold; }
  .divider { color: #484f58; }
</style>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>x0tta6bl4 Demo</title>
  {css}
</head>
<body>
  <div class="terminal">
    {content}
  </div>
</body>
</html>
"""


def create_terminal_html(filename: str, lines: list[str]) -> Path:
    """Create an HTML file rendering terminal output."""
    content_parts = []
    for line in lines:
        if line.startswith("$ "):
            content_parts.append(f'<span class="prompt">{line}</span>')
        elif "✓" in line or "PASS" in line:
            content_parts.append(f'<span class="success">{line}</span>')
        elif "╔" in line or "╚" in line or "╠" in line or "║" in line:
            content_parts.append(f'<span class="header">{line}</span>')
        elif line.startswith("─") or line.startswith("="):
            content_parts.append(f'<span class="divider">{line}</span>')
        else:
            content_parts.append(f'<span class="output">{line}</span>')

    html = HTML_TEMPLATE.format(
        css=TERMINAL_CSS,
        content="<br>".join(content_parts),
    )

    out_path = ASSETS_DIR / filename
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating demo HTML assets...")

    # 1. Quick Start terminal
    quickstart_lines = [
        '$ git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git',
        '$ cd x0tta6bl4/quickstart',
        '$ docker compose up -d',
        '$ ./demo.sh',
        "",
        "╔══════════════════════════════════════════════════════════╗",
        "║  x0tta6bl4 Demo — Quantum-Resistant Mesh VPN           ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        "▶ Step 1/6: Starting 2 mesh nodes...",
        "  ✓ Nodes started",
        "",
        "▶ Step 2/6: Waiting for nodes to become healthy...",
        "  ✓ Nodes healthy",
        "",
        "▶ Step 3/6: Checking mesh connectivity...",
        "  ✓ Node A reachable",
        "  ✓ Node B reachable",
        "",
        "▶ Step 4/6: Running validation framework...",
        "  ✓ Validation complete",
        "",
        "▶ Step 5/6: Generating HTML report...",
        "  ✓ Report: results/latest/report.html",
        "",
        "▶ Step 6/6: Results",
        "╔══════════════════════════════════════════════════════════╗",
        "║  DEMO COMPLETE                                          ║",
        "╠══════════════════════════════════════════════════════════╣",
        "║  ✓ Mesh Connected                                       ║",
        "║  ✓ PQC Handshake Established                            ║",
        "║  ✓ Validation Passed                                    ║",
        "║                                                          ║",
        "║  Node A: http://localhost:8280                          ║",
        "║  Node B: http://localhost:8281                          ║",
        "║  Metrics A: http://localhost:9290                       ║",
        "║  Report: results/latest/report.html                     ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        "To stop: docker compose down",
    ]
    p = create_terminal_html("quickstart_terminal.html", quickstart_lines)
    print(f"  ✓ {p.name}")

    # 2. Health check terminal
    health_lines = [
        "$ curl http://localhost:8280/health",
        "{",
        '  "node_id": "node-a",',
        '  "status": "ok",',
        '  "uptime": 120,',
        '  "peers": ["node-b"],',
        '  "consensus_count": 4',
        "}",
        "",
        "$ curl http://localhost:9190/metrics | grep x0tta6bl4_mesh",
        "# HELP x0tta6bl4_mesh_health_score Mesh node health score",
        "# TYPE x0tta6bl4_mesh_health_score gauge",
        'x0tta6bl4_mesh_health_score{node_id="node-a"} 20.0',
        "# HELP x0tta6bl4_mesh_uptime_seconds Seconds since start",
        "# TYPE x0tta6bl4_mesh_uptime_seconds gauge",
        'x0tta6bl4_mesh_uptime_seconds{node_id="node-a"} 120',
        "# HELP x0tta6bl4_mesh_peers_connected Active peers",
        "# TYPE x0tta6bl4_mesh_peers_connected gauge",
        'x0tta6bl4_mesh_peers_connected{node_id="node-a"} 1',
    ]
    p = create_terminal_html("health_terminal.html", health_lines)
    print(f"  ✓ {p.name}")

    # 3. Stop terminal
    stop_lines = [
        "$ docker compose down",
        "[+] Running 2/2",
        " ✔ Container x0tta-node-a  Removed",
        " ✔ Container x0tta-node-b  Removed",
        " Network quickstart_default  Removed",
    ]
    p = create_terminal_html("stop_terminal.html", stop_lines)
    print(f"  ✓ {p.name}")

    print("\nAll demo HTML assets generated.")


if __name__ == "__main__":
    main()
