#!/bin/bash
# Chaos Mesh Test Runner for x0tta6bl4
# Executes chaos scenarios and validates MAPE-K self-healing responses

set -e

NAMESPACE="${NAMESPACE:-x0tta6bl4}"
CHAOS_DIR="$(dirname "$0")/../scenarios"
TIMEOUT="${TIMEOUT:-120}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found"
        exit 1
    fi

    if ! kubectl get crd networkchaos.chaos-mesh.org &> /dev/null; then
        log_error "Chaos Mesh CRDs not installed"
        log_info "Install with: kubectl apply -f https://mirrors.chaos-mesh.org/v2.6.0/crd.yaml"
        exit 1
    fi

    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace $NAMESPACE not found"
        exit 1
    fi

    log_info "Prerequisites OK"
}

wait_for_pods_ready() {
    log_info "Waiting for mesh pods to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app=x0tta6bl4-node \
        -n "$NAMESPACE" \
        --timeout="${TIMEOUT}s" || {
        log_warn "Some pods not ready, continuing anyway..."
    }
}

get_metrics() {
    local metric_name="$1"
    kubectl exec -n "$NAMESPACE" deploy/mesh-node -- \
        curl -s localhost:8080/metrics 2>/dev/null | \
        grep "^${metric_name}" | head -1 || echo "0"
}

run_scenario() {
    local scenario_name="$1"
    local scenario_file="$2"
    local duration="${3:-60}"

    log_info "=== Running Scenario: $scenario_name ==="

    # Capture baseline metrics
    local baseline_anomalies=$(get_metrics "x0tta6bl4_pqc_anomalies_total")
    local baseline_healing=$(get_metrics "x0tta6bl4_mapek_healing_actions_total")

    log_info "Baseline - Anomalies: $baseline_anomalies, Healing: $baseline_healing"

    # Apply chaos
    log_info "Applying chaos: $scenario_file"
    kubectl apply -f "$scenario_file"

    # Wait for chaos duration + buffer
    log_info "Waiting ${duration}s for chaos + recovery..."
    sleep "$duration"

    # Delete chaos
    log_info "Removing chaos..."
    kubectl delete -f "$scenario_file" --ignore-not-found

    # Wait for recovery
    sleep 10
    wait_for_pods_ready

    # Check post-chaos metrics
    local post_anomalies=$(get_metrics "x0tta6bl4_pqc_anomalies_total")
    local post_healing=$(get_metrics "x0tta6bl4_mapek_healing_actions_total")

    log_info "Post-chaos - Anomalies: $post_anomalies, Healing: $post_healing"

    # Basic validation
    if [[ "$post_anomalies" != "$baseline_anomalies" ]] || \
       [[ "$post_healing" != "$baseline_healing" ]]; then
        log_info "✓ MAPE-K responded to chaos (metrics changed)"
        return 0
    else
        log_warn "✗ No MAPE-K response detected (metrics unchanged)"
        return 1
    fi
}

# Main execution
main() {
    local scenario="${1:-all}"

    log_info "=== x0tta6bl4 Chaos Mesh Test Suite ==="
    log_info "Namespace: $NAMESPACE"
    log_info "Scenario: $scenario"

    check_prerequisites
    wait_for_pods_ready

    local exit_code=0

    case "$scenario" in
        "partition"|"1")
            run_scenario "Network Partition" "$CHAOS_DIR/network-partition.yaml" 70 || exit_code=1
            ;;
        "pqc"|"2")
            run_scenario "PQC Failure" "$CHAOS_DIR/pqc-failure.yaml" 40 || exit_code=1
            ;;
        "crash"|"3")
            run_scenario "Node Crash" "$CHAOS_DIR/node-crash.yaml" 60 || exit_code=1
            ;;
        "all")
            log_info "Running all scenarios..."

            run_scenario "Network Partition" "$CHAOS_DIR/network-partition.yaml" 70 || exit_code=1
            sleep 30  # Recovery time between scenarios

            run_scenario "PQC Failure" "$CHAOS_DIR/pqc-failure.yaml" 40 || exit_code=1
            sleep 30

            run_scenario "Node Crash" "$CHAOS_DIR/node-crash.yaml" 60 || exit_code=1
            ;;
        *)
            log_error "Unknown scenario: $scenario"
            echo "Usage: $0 [partition|pqc|crash|all]"
            exit 1
            ;;
    esac

    log_info "=== Chaos Test Suite Complete ==="

    if [[ $exit_code -eq 0 ]]; then
        log_info "All scenarios passed!"
    else
        log_warn "Some scenarios had issues - check logs above"
    fi

    return $exit_code
}

main "$@"
