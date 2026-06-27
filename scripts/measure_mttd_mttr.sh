#!/bin/bash
# Measure MTTD and MTTR from Failure Injection Tests
# Дата: 2026-01-07
# Версия: Enhanced

set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-./failure_injection_results}"
OUTPUT_FILE="${OUTPUT_FILE:-./MTTD_MTTR_ANALYSIS_$(date +%Y%m%d_%H%M%S).md}"

# Target values
TARGET_MTTD=1800  # 30 minutes in seconds
TARGET_MTTR=3600  # 60 minutes in seconds

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# Initialize report
init_report() {
    cat > "$OUTPUT_FILE" << EOF
# MTTD/MTTR Analysis Report
**Дата анализа:** $(date -u +'%Y-%m-%d %H:%M:%S UTC')
**Версия:** x0tta6bl4 v3.4.0-fixed2

---

## 📊 Executive Summary

**Целевые значения:**
- MTTD (Mean Time To Detect): < 30 минут (1800 секунд)
- MTTR (Mean Time To Recover): < 60 минут (3600 секунд)

---

## 🔍 Test Results

EOF
}

# Calculate MTTD from test results
calculate_mttd() {
    local test_file="$1"
    local test_name="$2"
    
    # Extract detection time from test results
    # Format: "Detection time: 2026-01-07 10:30:00"
    local detection_time=$(grep -i "detection\|detected\|alert" "$test_file" 2>/dev/null | head -1 | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" || echo "")
    
    if [ -z "$detection_time" ]; then
        warn "Could not extract detection time from $test_file"
        return
    fi
    
    # Extract failure time
    local failure_time=$(grep -i "failure\|failed\|kill" "$test_file" 2>/dev/null | head -1 | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" || echo "")
    
    if [ -z "$failure_time" ]; then
        warn "Could not extract failure time from $test_file"
        return
    fi
    
    # Calculate difference in seconds
    local mttd=$(python3 -c "
from datetime import datetime
failure = datetime.strptime('$failure_time', '%Y-%m-%d %H:%M:%S')
detection = datetime.strptime('$detection_time', '%Y-%m-%d %H:%M:%S')
print(int((detection - failure).total_seconds()))
" 2>/dev/null || echo "0")
    
    echo "$mttd"
}

# Calculate MTTR from test results
calculate_mttr() {
    local test_file="$1"
    local test_name="$2"
    
    # Extract recovery time
    local recovery_time=$(grep -i "recovery\|recovered\|restored" "$test_file" 2>/dev/null | head -1 | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" || echo "")
    
    if [ -z "$recovery_time" ]; then
        warn "Could not extract recovery time from $test_file"
        return
    fi
    
    # Extract detection time
    local detection_time=$(grep -i "detection\|detected\|alert" "$test_file" 2>/dev/null | head -1 | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" || echo "")
    
    if [ -z "$detection_time" ]; then
        warn "Could not extract detection time from $test_file"
        return
    fi
    
    # Calculate difference in seconds
    local mttr=$(python3 -c "
from datetime import datetime
detection = datetime.strptime('$detection_time', '%Y-%m-%d %H:%M:%S')
recovery = datetime.strptime('$recovery_time', '%Y-%m-%d %H:%M:%S')
print(int((recovery - detection).total_seconds()))
" 2>/dev/null || echo "0")
    
    echo "$mttr"
}

# Analyze test results
analyze_tests() {
    log "Analyzing test results..."
    
    if [ ! -d "$RESULTS_DIR" ]; then
        warn "Results directory not found: $RESULTS_DIR"
        return
    fi
    
    local test_files=$(find "$RESULTS_DIR" -name "*.log" -o -name "*.txt" -o -name "*result*.md" 2>/dev/null)
    
    if [ -z "$test_files" ]; then
        warn "No test result files found"
        echo "### Test Results" >> "$OUTPUT_FILE"
        echo "- ⚠️ No test result files found" >> "$OUTPUT_FILE"
        return
    fi
    
    echo "### Test Results" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    local total_mttd=0
    local total_mttr=0
    local test_count=0
    
    for test_file in $test_files; do
        local test_name=$(basename "$test_file")
        local mttd=$(calculate_mttd "$test_file" "$test_name")
        local mttr=$(calculate_mttr "$test_file" "$test_name")
        
        if [ "$mttd" != "0" ] && [ "$mttr" != "0" ]; then
            total_mttd=$((total_mttd + mttd))
            total_mttr=$((total_mttr + mttr))
            test_count=$((test_count + 1))
            
            local mttd_min=$((mttd / 60))
            local mttr_min=$((mttr / 60))
            
            echo "#### $test_name" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            echo "- MTTD: ${mttd_min} минут (${mttd} секунд)" >> "$OUTPUT_FILE"
            echo "- MTTR: ${mttr_min} минут (${mttr} секунд)" >> "$OUTPUT_FILE"
            
            # Check against targets
            if [ $mttd -gt $TARGET_MTTD ]; then
                echo "- ⚠️ **MTTD превышает целевое значение** (target: 30 минут)" >> "$OUTPUT_FILE"
            else
                echo "- ✅ **MTTD в пределах целевого значения**" >> "$OUTPUT_FILE"
            fi
            
            if [ $mttr -gt $TARGET_MTTR ]; then
                echo "- ⚠️ **MTTR превышает целевое значение** (target: 60 минут)" >> "$OUTPUT_FILE"
            else
                echo "- ✅ **MTTR в пределах целевого значения**" >> "$OUTPUT_FILE"
            fi
            
            echo "" >> "$OUTPUT_FILE"
        fi
    done
    
    # Calculate averages
    if [ $test_count -gt 0 ]; then
        local avg_mttd=$((total_mttd / test_count))
        local avg_mttr=$((total_mttr / test_count))
        local avg_mttd_min=$((avg_mttd / 60))
        local avg_mttr_min=$((avg_mttr / 60))
        
        echo "### Summary" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        echo "- **Average MTTD:** ${avg_mttd_min} минут (${avg_mttd} секунд)" >> "$OUTPUT_FILE"
        echo "- **Average MTTR:** ${avg_mttr_min} минут (${avg_mttr} секунд)" >> "$OUTPUT_FILE"
        echo "- **Tests analyzed:** ${test_count}" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        
        # Overall assessment
        if [ $avg_mttd -gt $TARGET_MTTD ] || [ $avg_mttr -gt $TARGET_MTTR ]; then
            echo "### ⚠️ Assessment" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            echo "**MTTD/MTTR превышают целевые значения.**" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            echo "Рекомендации:" >> "$OUTPUT_FILE"
            echo "1. Улучшить механизмы обнаружения (MTTD)" >> "$OUTPUT_FILE"
            echo "2. Улучшить механизмы восстановления (MTTR)" >> "$OUTPUT_FILE"
            echo "3. Рассмотреть NO-GO для beta launch" >> "$OUTPUT_FILE"
        else
            echo "### ✅ Assessment" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            echo "**MTTD/MTTR в пределах целевых значений.**" >> "$OUTPUT_FILE"
            echo "" >> "$OUTPUT_FILE"
            echo "Рекомендации:" >> "$OUTPUT_FILE"
            echo "1. Продолжить к GO/NO-GO decision" >> "$OUTPUT_FILE"
            echo "2. Мониторить MTTD/MTTR в production" >> "$OUTPUT_FILE"
        fi
    fi
}

# Main execution
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     MTTD/MTTR Analysis                                        ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    init_report
    analyze_tests
    
    log "✅ Analysis complete"
    log "📄 Report saved to: $OUTPUT_FILE"
}

if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi

