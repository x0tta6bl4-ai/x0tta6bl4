#!/bin/bash
# Analyze Stability Test Results
# Analyzes stability_test.log and creates a report

LOG_FILE=${1:-stability_test.log}
REPORT_FILE="stability_test_analysis_$(date +%Y%m%d_%H%M%S).md"

if [ ! -f "$LOG_FILE" ]; then
    echo "Error: Log file $LOG_FILE not found"
    exit 1
fi

echo "Analyzing stability test results from $LOG_FILE..."
echo "Report will be saved to: $REPORT_FILE"
echo ""

# Create report header
cat > $REPORT_FILE << EOF
# Stability Test Analysis Report

**Дата анализа:** $(date +"%Y-%m-%d %H:%M:%S")  
**Лог файл:** $LOG_FILE

---

## Summary

EOF

# Count iterations
TOTAL_ITERATIONS=$(grep -c "=== Iteration" $LOG_FILE || echo "0")
echo "Total iterations: $TOTAL_ITERATIONS" | tee -a $REPORT_FILE

# Check for errors
ERROR_COUNT=$(grep -i "error\|failed\|crash" $LOG_FILE | wc -l || echo "0")
echo "Error count: $ERROR_COUNT" | tee -a $REPORT_FILE

# Extract initial and final states
echo "" | tee -a $REPORT_FILE
echo "## Initial State" | tee -a $REPORT_FILE
grep -A 10 "Iteration 1/" $LOG_FILE | head -20 | tee -a $REPORT_FILE

echo "" | tee -a $REPORT_FILE
echo "## Final State" | tee -a $REPORT_FILE
tail -30 $LOG_FILE | tee -a $REPORT_FILE

# Extract GNN recall scores
echo "" | tee -a $REPORT_FILE
echo "## GNN Recall Score Trend" | tee -a $REPORT_FILE
grep "gnn_recall_score" $LOG_FILE | awk '{print $NF}' | sort -n | tee -a $REPORT_FILE

# Extract memory usage
echo "" | tee -a $REPORT_FILE
echo "## Memory Usage Trend" | tee -a $REPORT_FILE
grep "process_resident_memory_bytes" $LOG_FILE | awk '{print $NF}' | tee -a $REPORT_FILE

# Pod restart analysis
echo "" | tee -a $REPORT_FILE
echo "## Pod Restart Analysis" | tee -a $REPORT_FILE
grep "RESTARTS" $LOG_FILE | tail -5 | tee -a $REPORT_FILE

# Health check analysis
echo "" | tee -a $REPORT_FILE
echo "## Health Check Analysis" | tee -a $REPORT_FILE
HEALTH_OK=$(grep -c '"status": "ok"' $LOG_FILE || echo "0")
HEALTH_TOTAL=$(grep -c "Health check:" $LOG_FILE || echo "0")
if [ "$HEALTH_TOTAL" -gt 0 ]; then
    HEALTH_PERCENT=$((HEALTH_OK * 100 / HEALTH_TOTAL))
    echo "Health checks: $HEALTH_OK/$HEALTH_TOTAL ($HEALTH_PERCENT%)" | tee -a $REPORT_FILE
fi

# Recommendations
echo "" | tee -a $REPORT_FILE
echo "## Recommendations" | tee -a $REPORT_FILE
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo "✅ No errors detected. System is stable." | tee -a $REPORT_FILE
else
    echo "⚠️  $ERROR_COUNT errors detected. Review logs for details." | tee -a $REPORT_FILE
fi

echo "" | tee -a $REPORT_FILE
echo "Analysis completed. Report saved to: $REPORT_FILE"

