#!/usr/bin/env bash
# x0tta6bl4 Demo Assets Capture
# Records terminal session during demo.sh for GIF generation
# Usage: ./capture_demo.sh [output_dir]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-$PROJECT_DIR/docs/assets/demo}"

mkdir -p "$OUTPUT_DIR"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  x0tta6bl4 Demo Assets Capture                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo
echo "Output directory: $OUTPUT_DIR"
echo

# Check for asciinema
if command -v asciinema &> /dev/null; then
    echo "✓ asciinema found — recording terminal session"
    RECORD=true
else
    echo "⚠ asciinema not found — installing..."
    pip install asciinema 2>/dev/null || {
        echo "Cannot install asciinema. Using manual capture."
        RECORD=false
    }
fi

# Step 1: Capture health check
echo
echo "▶ Capturing health check..."
HEALTH_OUTPUT=$(curl -s http://localhost:8280/health 2>/dev/null || echo '{"error":"node not running"}')
echo "$HEALTH_OUTPUT" | python3 -m json.tool > "$OUTPUT_DIR/health_response.json" 2>/dev/null || echo "$HEALTH_OUTPUT" > "$OUTPUT_DIR/health_response.json"
echo "  ✓ Saved: health_response.json"

# Step 2: Capture metrics
echo
echo "▶ Capturing metrics..."
METRICS_OUTPUT=$(curl -s http://localhost:9190/metrics 2>/dev/null | grep x0tta6bl4_mesh || echo "# No metrics available")
echo "$METRICS_OUTPUT" > "$OUTPUT_DIR/metrics_output.txt"
echo "  ✓ Saved: metrics_output.txt"

# Step 3: Capture peer list
echo
echo "▶ Capturing peer list..."
PEERS_OUTPUT=$(curl -s http://localhost:8280/peers 2>/dev/null || echo '{"error":"node not running"}')
echo "$PEERS_OUTPUT" | python3 -m json.tool > "$OUTPUT_DIR/peers_response.json" 2>/dev/null || echo "$PEERS_OUTPUT" > "$OUTPUT_DIR/peers_response.json"
echo "  ✓ Saved: peers_response.json"

# Step 4: Generate ASCII art for README
echo
echo "▶ Generating ASCII art examples..."
cat > "$OUTPUT_DIR/terminal_example.txt" << 'EOF'
$ git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
$ cd x0tta6bl4/quickstart
$ docker compose up -d
$ ./demo.sh

╔══════════════════════════════════════════════════════════╗
║  x0tta6bl4 Demo — Quantum-Resistant Mesh VPN           ║
╚══════════════════════════════════════════════════════════╝

▶ Step 1/6: Starting 2 mesh nodes...
  ✓ Nodes started

▶ Step 2/6: Waiting for nodes to become healthy...
  ✓ Nodes healthy

▶ Step 3/6: Checking mesh connectivity...
  ✓ Node A reachable
  ✓ Node B reachable

▶ Step 4/6: Running validation framework...
  ✓ Validation complete

▶ Step 5/6: Generating HTML report...
  ✓ Report: results/latest/report.html

▶ Step 6/6: Results
╔══════════════════════════════════════════════════════════╗
║  DEMO COMPLETE                                          ║
╠══════════════════════════════════════════════════════════╣
║  ✓ Mesh Connected                                       ║
║  ✓ PQC Handshake Established                            ║
║  ✓ Validation Passed                                    ║
║                                                          ║
║  Node A: http://localhost:8280                          ║
║  Node B: http://localhost:8281                          ║
║  Metrics A: http://localhost:9290                       ║
║  Report: results/latest/report.html                    ║
╚══════════════════════════════════════════════════════════╝

To stop: docker compose down
EOF
echo "  ✓ Saved: terminal_example.txt"

# Step 5: Generate health check example
echo
echo "▶ Generating API examples..."
cat > "$OUTPUT_DIR/api_example.txt" << 'EOF'
$ curl http://localhost:8280/health
{
  "node_id": "node-a",
  "status": "ok",
  "uptime": 120,
  "peers": ["node-b"],
  "consensus_count": 4
}

$ curl http://localhost:9190/metrics | grep x0tta6bl4_mesh
# HELP x0tta6bl4_mesh_health_score Mesh node health score baseline
# TYPE x0tta6bl4_mesh_health_score gauge
x0tta6bl4_mesh_health_score{node_id="node-a"} 20.0
# HELP x0tta6bl4_mesh_uptime_seconds Seconds since the mesh node started
# TYPE x0tta6bl4_mesh_uptime_seconds gauge
x0tta6bl4_mesh_uptime_seconds{node_id="node-a"} 120
# HELP x0tta6bl4_mesh_peers_connected Number of currently valid/active peers
# TYPE x0tta6bl4_mesh_peers_connected gauge
x0tta6bl4_mesh_peers_connected{node_id="node-a"} 1
EOF
echo "  ✓ Saved: api_example.txt"

echo
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Demo assets generated in: $OUTPUT_DIR"
echo "╚══════════════════════════════════════════════════════════╝"
echo
echo "To create a GIF from terminal recording:"
echo "  1. asciinema rec demo.cast"
echo "  2. ./demo.sh"
echo "  3. exit"
echo "  4. agg demo.cast demo.gif"
echo
