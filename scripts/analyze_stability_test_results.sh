#!/bin/bash
# Enhanced Stability Test Results Analysis
# Дата: 2026-01-07
# Версия: Enhanced

set -euo pipefail

METRICS_DIR="${METRICS_DIR:-./stability_test_metrics}"
OUTPUT_FILE="${OUTPUT_FILE:-./STABILITY_TEST_ANALYSIS_$(date +%Y%m%d_%H%M%S).md}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Initialize output file
init_report() {
    cat > "$OUTPUT_FILE" << EOF
# Stability Test Analysis Report
**Дата анализа:** $(date -u +'%Y-%m-%d %H:%M:%S UTC')
**Версия:** x0tta6bl4 v3.4.0-fixed2

---

## 📊 Executive Summary

**Статус:** ⏳ Анализ в процессе

---

## 🔍 Memory Analysis

EOF
}

# Analyze memory trends
analyze_memory() {
    log "Analyzing memory trends..."
    
    if [ ! -d "$METRICS_DIR" ]; then
        warn "Metrics directory not found: $METRICS_DIR"
        return
    fi
    
    # Find memory metrics files
    local memory_files=$(find "$METRICS_DIR" -name "*memory*.json" -o -name "*memory*.txt" 2>/dev/null | head -5)
    
    if [ -z "$memory_files" ]; then
        warn "No memory metrics files found"
        echo "" >> "$OUTPUT_FILE"
        echo "### Memory Metrics" >> "$OUTPUT_FILE"
        echo "- ⚠️ No memory metrics files found" >> "$OUTPUT_FILE"
        return
    fi
    
    echo "" >> "$OUTPUT_FILE"
    echo "### Memory Trends" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Analyze memory growth
    local memory_values=()
    for file in $memory_files; do
        if [[ "$file" == *.json ]]; then
            local mem=$(python3 -c "import json, sys; data=json.load(open('$file')); print(data.get('memory_usage_bytes', 0))" 2>/dev/null || echo "0")
            memory_values+=("$mem")
        fi
    done
    
    if [ ${#memory_values[@]} -gt 1 ]; then
        local first=${memory_values[0]}
        local last=${memory_values[-1]}
        local growth=$((last - first))
        local growth_percent=$((growth * 100 / first))
        
        if [ $growth_percent -gt 10 ]; then
            echo "- ❌ **Memory Leak Detected:** Growth of ${growth_percent}% detected" >> "$OUTPUT_FILE"
            echo "  - Initial: ${first} bytes" >> "$OUTPUT_FILE"
            echo "  - Final: ${last} bytes" >> "$OUTPUT_FILE"
            echo "  - Growth: ${growth} bytes" >> "$OUTPUT_FILE"
        else
            echo "- ✅ **Memory Stable:** Growth of ${growth_percent}% (within acceptable range)" >> "$OUTPUT_FILE"
        fi
    fi
}

# Analyze CPU patterns
analyze_cpu() {
    log "Analyzing CPU patterns..."
    
    local cpu_files=$(find "$METRICS_DIR" -name "*cpu*.json" -o -name "*cpu*.txt" 2>/dev/null | head -5)
    
    if [ -z "$cpu_files" ]; then
        warn "No CPU metrics files found"
        echo "" >> "$OUTPUT_FILE"
        echo "### CPU Metrics" >> "$OUTPUT_FILE"
        echo "- ⚠️ No CPU metrics files found" >> "$OUTPUT_FILE"
        return
    fi
    
    echo "" >> "$OUTPUT_FILE"
    echo "### CPU Patterns" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Analyze CPU spikes
    local max_cpu=0
    for file in $cpu_files; do
        if [[ "$file" == *.json ]]; then
            local cpu=$(python3 -c "import json, sys; data=json.load(open('$file')); print(data.get('cpu_usage_percent', 0))" 2>/dev/null || echo "0")
            if (( $(echo "$cpu > $max_cpu" | bc -l 2>/dev/null || echo "0") )); then
                max_cpu=$cpu
            fi
        fi
    done
    
    if (( $(echo "$max_cpu > 80" | bc -l 2>/dev/null || echo "0") )); then
        echo "- ⚠️ **High CPU Usage:** Peak CPU usage: ${max_cpu}%" >> "$OUTPUT_FILE"
    else
        echo "- ✅ **CPU Usage Normal:** Peak CPU usage: ${max_cpu}%" >> "$OUTPUT_FILE"
    fi
}

# Analyze error patterns
analyze_errors() {
    log "Analyzing error patterns..."
    
    local error_files=$(find "$METRICS_DIR" -name "*error*.json" -o -name "*error*.txt" -o -name "*log*.txt" 2>/dev/null | head -10)
    
    if [ -z "$error_files" ]; then
        warn "No error logs found"
        echo "" >> "$OUTPUT_FILE"
        echo "### Error Analysis" >> "$OUTPUT_FILE"
        echo "- ⚠️ No error logs found" >> "$OUTPUT_FILE"
        return
    fi
    
    echo "" >> "$OUTPUT_FILE"
    echo "### Error Patterns" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Count errors
    local error_count=0
    for file in $error_files; do
        if [[ "$file" == *.txt ]]; then
            local count=$(grep -i "error\|exception\|failed" "$file" 2>/dev/null | wc -l || echo "0")
            error_count=$((error_count + count))
        fi
    done
    
    if [ $error_count -gt 0 ]; then
        echo "- ⚠️ **Errors Detected:** ${error_count} error messages found" >> "$OUTPUT_FILE"
        echo "  - Review logs for patterns" >> "$OUTPUT_FILE"
    else
        echo "- ✅ **No Errors:** No error messages detected" >> "$OUTPUT_FILE"
    fi
}

# Generate recommendations
generate_recommendations() {
    log "Generating recommendations..."
    
    echo "" >> "$OUTPUT_FILE"
    echo "## 💡 Recommendations" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Check for issues
    if grep -q "Memory Leak Detected\|High CPU Usage\|Errors Detected" "$OUTPUT_FILE" 2>/dev/null; then
        echo "### ⚠️ Issues Found" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        echo "1. **Review detailed metrics** in $METRICS_DIR" >> "$OUTPUT_FILE"
        echo "2. **Check pod logs** for specific errors" >> "$OUTPUT_FILE"
        echo "3. **Consider NO-GO** if critical issues found" >> "$OUTPUT_FILE"
        echo "4. **Fix issues** before proceeding to failure injection tests" >> "$OUTPUT_FILE"
    else
        echo "### ✅ No Critical Issues" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        echo "1. **Proceed to failure injection tests** (Jan 9)" >> "$OUTPUT_FILE"
        echo "2. **Continue monitoring** for any anomalies" >> "$OUTPUT_FILE"
        echo "3. **Prepare for GO/NO-GO decision** (Jan 10)" >> "$OUTPUT_FILE"
    fi
}

# Main execution
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Stability Test Results Analysis                          ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    init_report
    analyze_memory
    analyze_cpu
    analyze_errors
    generate_recommendations
    
    log "✅ Analysis complete"
    log "📄 Report saved to: $OUTPUT_FILE"
}

if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi

