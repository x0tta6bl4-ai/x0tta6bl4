#!/bin/bash
# Provision Grafana dashboards via API
# This script creates both Stage 3 dashboards automatically

set -e

# Configuration
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="admin"
PROMETHEUS_URL="http://localhost:9090"

echo "🚀 Starting Grafana provisioning..."
echo ""

# Wait for Grafana to be ready
echo "⏳ Waiting for Grafana to be ready..."
for i in {1..30}; do
  if curl -s "$GRAFANA_URL/api/health" > /dev/null 2>&1; then
    echo "✅ Grafana is ready"
    break
  fi
  echo "Attempt $i/30..."
  sleep 2
done

# 1. Add Prometheus data source
echo ""
echo "1️⃣  Adding Prometheus data source..."

DATASOURCE_JSON=$(cat <<'EOF'
{
  "name": "Prometheus",
  "type": "prometheus",
  "url": "http://localhost:9090",
  "access": "proxy",
  "isDefault": true,
  "editable": true
}
EOF
)

curl -s -X POST "$GRAFANA_URL/api/datasources" \
  -H "Content-Type: application/json" \
  -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
  -d "$DATASOURCE_JSON" | python3 -m json.tool | head -10

echo "✅ Data source added"

# 2. Create Dashboard 1: Violations & Threats
echo ""
echo "2️⃣  Creating Dashboard 1: Violations & Threats..."

DASHBOARD1=$(cat <<'EODASH'
{
  "dashboard": {
    "title": "Charter Violations & Threats Monitor",
    "tags": ["charter", "security", "violations"],
    "timezone": "UTC",
    "panels": [
      {
        "id": 1,
        "title": "Critical Violations Over Time",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
        "targets": [
          {
            "expr": "increase(westworld_charter_policy_violations_total{severity=\"critical\"}[5m])",
            "legendFormat": "Critical Violations",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {"mode": "palette-classic"},
            "custom": {"drawStyle": "line"}
          }
        }
      },
      {
        "id": 2,
        "title": "Violation Distribution by Severity",
        "type": "piechart",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum(westworld_charter_policy_violations_total) by (severity)",
            "format": "table",
            "refId": "A"
          }
        ]
      },
      {
        "id": 3,
        "title": "Overall System Threat Level",
        "type": "gauge",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "max(westworld_charter_violations_severity_gauge)",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "max": 10,
            "min": 0,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 3},
                {"color": "red", "value": 7}
              ]
            }
          }
        }
      },
      {
        "id": 4,
        "title": "Active Alerts",
        "type": "stat",
        "gridPos": {"x": 0, "y": 16, "w": 24, "h": 4},
        "targets": [
          {
            "expr": "count(ALERTS{state=\"firing\"})",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {"mode": "thresholds"},
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "red", "value": 1}
              ]
            }
          }
        }
      }
    ],
    "refresh": "30s",
    "time": {
      "from": "now-6h",
      "to": "now"
    },
    "schemaVersion": 38,
    "version": 0,
    "uid": "charter-violations",
    "fiscalYearStartMonth": 0
  }
}
EODASH
)

curl -s -X POST "$GRAFANA_URL/api/dashboards/db" \
  -H "Content-Type: application/json" \
  -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
  -d "$DASHBOARD1" | python3 -m json.tool | head -10

echo "✅ Dashboard 1 created"

# 3. Create Dashboard 2: Enforcement Performance
echo ""
echo "3️⃣  Creating Dashboard 2: Enforcement Performance..."

DASHBOARD2=$(cat <<'EODASH'
{
  "dashboard": {
    "title": "Charter Enforcement Performance Metrics",
    "tags": ["charter", "performance", "enforcement"],
    "timezone": "UTC",
    "panels": [
      {
        "id": 1,
        "title": "Policy Enforcement Actions",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
        "targets": [
          {
            "expr": "increase(westworld_charter_enforcement_actions_total{action_type=\"block\"}[5m])",
            "legendFormat": "Block",
            "refId": "A"
          },
          {
            "expr": "increase(westworld_charter_enforcement_actions_total{action_type=\"allow\"}[5m])",
            "legendFormat": "Allow",
            "refId": "B"
          },
          {
            "expr": "increase(westworld_charter_enforcement_actions_total{action_type=\"challenge\"}[5m])",
            "legendFormat": "Challenge",
            "refId": "C"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "custom": {"stacking": "normal"}
          }
        }
      },
      {
        "id": 2,
        "title": "Data Revocations (Last 24h)",
        "type": "stat",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "increase(westworld_charter_data_revocations_total[24h])",
            "refId": "A"
          }
        ]
      },
      {
        "id": 3,
        "title": "Average Decision Latency",
        "type": "gauge",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "histogram_quantile(0.5, rate(westworld_charter_committee_decision_duration_seconds_bucket[5m]))",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "max": 10,
            "min": 0,
            "unit": "s",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 2},
                {"color": "red", "value": 5}
              ]
            }
          }
        }
      },
      {
        "id": 4,
        "title": "System Health Score",
        "type": "stat",
        "gridPos": {"x": 0, "y": 16, "w": 24, "h": 4},
        "targets": [
          {
            "expr": "(1 - (count(ALERTS{state=\"firing\"}) / 30)) * 100",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "red", "value": null},
                {"color": "yellow", "value": 50},
                {"color": "green", "value": 80}
              ]
            }
          }
        }
      }
    ],
    "refresh": "30s",
    "time": {
      "from": "now-24h",
      "to": "now"
    },
    "schemaVersion": 38,
    "version": 0,
    "uid": "charter-enforcement",
    "fiscalYearStartMonth": 0
  }
}
EODASH
)

curl -s -X POST "$GRAFANA_URL/api/dashboards/db" \
  -H "Content-Type: application/json" \
  -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
  -d "$DASHBOARD2" | python3 -m json.tool | head -10

echo "✅ Dashboard 2 created"

echo ""
echo "✅ Grafana provisioning complete!"
echo ""
echo "📊 Access dashboards at:"
echo "  Dashboard 1: http://localhost:3000/d/charter-violations"
echo "  Dashboard 2: http://localhost:3000/d/charter-enforcement"
echo ""
echo "🔑 Login:"
echo "  Username: admin"
echo "  Password: admin"
