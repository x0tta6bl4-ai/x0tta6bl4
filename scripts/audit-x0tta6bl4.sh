#!/bin/bash
# audit-x0tta6bl4.sh — полная оценка готовности компонентов

AUDIT_DIR="audit-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$AUDIT_DIR"

echo "📋 Аудит x0tta6bl4 компонентов..."

# Self-Healing Mesh: проверь MTTR и latency
echo "🔍 Self-Healing Mesh..."
if command -v x0tta6bl4 &> /dev/null; then
    x0tta6bl4 metrics --metric=mttr,latency,loss --period=30d > "$AUDIT_DIR/mesh-metrics.json" 2>/dev/null || echo "{}" > "$AUDIT_DIR/mesh-metrics.json"
    if command -v jq &> /dev/null; then
        MTTR=$(cat "$AUDIT_DIR/mesh-metrics.json" | jq -r '.mttr.p95 // "N/A"')
        echo "  MTTR p95: $MTTR"
        if [[ "$MTTR" =~ ^[0-9]+\.?[0-9]*$ ]] && (( $(echo "$MTTR < 3.0" | bc -l) )); then
            echo "  ✅ MTTR acceptable"
        else
            echo "  ⚠️  MTTR needs improvement"
        fi
    fi
else
    echo "  ⚠️  x0tta6bl4 CLI not found"
fi

# Zero-Trust: проверь crypto-состояние
echo "🔍 Zero-Trust Security..."
if command -v x0tta6bl4 &> /dev/null; then
    x0tta6bl4 zero-trust status --format=json > "$AUDIT_DIR/zero-trust-status.json" 2>/dev/null || echo "{}" > "$AUDIT_DIR/zero-trust-status.json"
    if grep -q "mode.*strict" "$AUDIT_DIR/zero-trust-status.json" 2>/dev/null; then
        echo "  ✅ Zero-Trust STRICT enabled"
    else
        echo "  ❌ Zero-Trust not strict"
    fi
else
    echo "  ⚠️  x0tta6bl4 CLI not found"
fi

# DAO: проверь governance-состояние
echo "🔍 DAO Governance..."
if command -v x0tta6bl4 &> /dev/null; then
    x0tta6bl4 dao list-proposals --status=all --format=json > "$AUDIT_DIR/dao-proposals.json" 2>/dev/null || echo "[]" > "$AUDIT_DIR/dao-proposals.json"
    if command -v jq &> /dev/null; then
        PROPOSAL_COUNT=$(cat "$AUDIT_DIR/dao-proposals.json" | jq 'length // 0')
        echo "  📊 Total proposals: $PROPOSAL_COUNT"
    fi
else
    echo "  ⚠️  x0tta6bl4 CLI not found"
fi

# Post-Quantum Crypto: проверь ключи
echo "🔍 Post-Quantum Crypto..."
if [ -d "keys" ]; then
    ls -la keys/ 2>/dev/null | grep -E 'ntru|kyber' > "$AUDIT_DIR/crypto-keys.log" || echo "" > "$AUDIT_DIR/crypto-keys.log"
    KEY_COUNT=$(cat "$AUDIT_DIR/crypto-keys.log" | wc -l)
    echo "  🔐 NTRU/Kyber keys: $KEY_COUNT"
else
    echo "  ⚠️  Keys directory not found"
fi

# Anti-Censorship: проверь stego-mode
echo "🔍 Anti-Censorship Stego..."
if command -v x0tta6bl4 &> /dev/null; then
    x0tta6bl4 anti-censor status --format=json > "$AUDIT_DIR/stego-status.json" 2>/dev/null || echo "{}" > "$AUDIT_DIR/stego-status.json"
    if grep -q "stego.*enabled" "$AUDIT_DIR/stego-status.json" 2>/dev/null; then
        echo "  ✅ Stego-Mesh enabled"
    else
        echo "  ❌ Stego-Mesh disabled"
    fi
else
    echo "  ⚠️  x0tta6bl4 CLI not found"
fi

# Федеративное обучение: проверь accuracy
echo "🔍 Federated Learning..."
if command -v x0tta6bl4 &> /dev/null; then
    x0tta6bl4 federated metrics --metric=accuracy,loss --format=json > "$AUDIT_DIR/federated-metrics.json" 2>/dev/null || echo "{}" > "$AUDIT_DIR/federated-metrics.json"
    if command -v jq &> /dev/null; then
        ACCURACY=$(cat "$AUDIT_DIR/federated-metrics.json" | jq -r '.accuracy // "N/A"')
        echo "  🧠 Federated Model Accuracy: $ACCURACY%"
    fi
else
    echo "  ⚠️  x0tta6bl4 CLI not found"
fi

# CI/CD: проверь последний deployment
echo "🔍 CI/CD Pipeline..."
if command -v x0tta6bl4 &> /dev/null; then
    x0tta6bl4 ci status --format=json > "$AUDIT_DIR/ci-status.json" 2>/dev/null || echo "{}" > "$AUDIT_DIR/ci-status.json"
    if command -v jq &> /dev/null; then
        LAST_DEPLOY_TIME=$(cat "$AUDIT_DIR/ci-status.json" | jq -r '.last_deployment.duration // "N/A"')
        echo "  ⚡ Last deployment time: ${LAST_DEPLOY_TIME}s"
    fi
else
    echo "  ⚠️  x0tta6bl4 CLI not found"
fi

# Observability: проверь метрики в Prometheus
echo "🔍 Observability (Prometheus)..."
if curl -s http://localhost:9090/api/v1/targets?state=active > /dev/null 2>&1; then
    if command -v jq &> /dev/null; then
        TARGETS=$(curl -s http://localhost:9090/api/v1/targets?state=active | jq -r '.data.activeTargets | length // 0')
        echo "  📊 Active Prometheus targets: $TARGETS"
    else
        echo "  ⚠️  jq not found, cannot parse Prometheus response"
    fi
else
    echo "  ⚠️  Prometheus not accessible at localhost:9090"
fi

echo ""
echo "✅ Аудит завершён! Результаты: $AUDIT_DIR"
ls -la "$AUDIT_DIR"

