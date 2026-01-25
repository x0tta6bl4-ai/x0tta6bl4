#!/bin/bash
# Run baseline benchmarks for x0tta6bl4
# Establishes baseline metrics before Phase 2 development

set -e

echo "🚀 Starting baseline benchmarks for x0tta6bl4"
echo "=============================================="

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8080}"
OUTPUT_DIR="${OUTPUT_DIR:-benchmarks/results}"
BASELINE_DIR="${BASELINE_DIR:-benchmarks/baseline}"

# Create directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$BASELINE_DIR"

# Check if service is running
echo "📡 Checking if service is available at $BASE_URL..."
if ! curl -f -s "$BASE_URL/health" > /dev/null; then
    echo "❌ Service not available at $BASE_URL"
    echo "   Start service with: docker-compose up -d"
    echo "   Or: uvicorn src.core.app:app --host 0.0.0.0 --port 8080"
    exit 1
fi
echo "✅ Service is available"

# Run performance benchmarks
echo ""
echo "📊 Running performance benchmarks..."
python -m tests.performance.benchmark_metrics \
    --url "$BASE_URL" \
    --output-dir "$OUTPUT_DIR" \
    --format both

# Run MTTR benchmarks (fewer iterations for baseline)
echo ""
echo "⏱️  Running MTTR benchmarks..."
python -m tests.performance.benchmark_mttr \
    --url "$BASE_URL" \
    --output-dir "$OUTPUT_DIR" \
    --iterations 3

# Find latest results
LATEST_JSON=$(ls -t "$OUTPUT_DIR"/benchmark_*.json 2>/dev/null | head -1)
LATEST_MTTR=$(ls -t "$OUTPUT_DIR"/mttr_benchmark_*.json 2>/dev/null | head -1)

if [ -n "$LATEST_JSON" ]; then
    # Copy to baseline
    BASELINE_FILE="$BASELINE_DIR/baseline_$(date +%Y%m%d).json"
    cp "$LATEST_JSON" "$BASELINE_FILE"
    echo ""
    echo "✅ Baseline saved to: $BASELINE_FILE"
    
    # Also create symlink for easy access
    ln -sf "$(basename "$BASELINE_FILE")" "$BASELINE_DIR/baseline.json"
    echo "✅ Symlink created: $BASELINE_DIR/baseline.json"
fi

if [ -n "$LATEST_MTTR" ]; then
    MTTR_BASELINE="$BASELINE_DIR/mttr_baseline_$(date +%Y%m%d).json"
    cp "$LATEST_MTTR" "$MTTR_BASELINE"
    echo "✅ MTTR baseline saved to: $MTTR_BASELINE"
fi

echo ""
echo "=============================================="
echo "✅ Baseline benchmarks completed!"
echo ""
echo "Results:"
echo "  - Performance: $OUTPUT_DIR/"
echo "  - Baseline: $BASELINE_DIR/"
echo ""
echo "Next steps:"
echo "  1. Review baseline metrics"
echo "  2. Start Phase 2 development"
echo "  3. Compare new metrics against baseline"
echo ""

