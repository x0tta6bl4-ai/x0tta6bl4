package metrics

import (
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCollectorMetrics(t *testing.T) {
	c := NewCollector()

	// Update from snapshot
	c.UpdateFromSnapshot(10, 8, 0.85, 3)

	if c.PeersTotal.Get() != 10 {
		t.Errorf("PeersTotal = %f, want 10", c.PeersTotal.Get())
	}
	if c.PeersHealthy.Get() != 8 {
		t.Errorf("PeersHealthy = %f, want 8", c.PeersHealthy.Get())
	}
	if c.PeersUnhealthy.Get() != 2 {
		t.Errorf("PeersUnhealthy = %f, want 2", c.PeersUnhealthy.Get())
	}
	if c.HealthScore.Get() != 0.85 {
		t.Errorf("HealthScore = %f, want 0.85", c.HealthScore.Get())
	}
	if c.PQCSessions.Get() != 3 {
		t.Errorf("PQCSessions = %f, want 3", c.PQCSessions.Get())
	}
}

func TestCollectorCounters(t *testing.T) {
	c := NewCollector()

	c.RecordHealing("reroute", true)
	c.RecordHealing("reconnect", false)

	if c.HealingActions.Get() != 2 {
		t.Errorf("HealingActions = %f, want 2", c.HealingActions.Get())
	}
	if c.HealingErrors.Get() != 1 {
		t.Errorf("HealingErrors = %f, want 1", c.HealingErrors.Get())
	}

	c.RecordMessage(true, 1024)
	c.RecordMessage(false, 512)

	if c.MessagesSent.Get() != 1 {
		t.Errorf("MessagesSent = %f, want 1", c.MessagesSent.Get())
	}
	if c.BytesSent.Get() != 1024 {
		t.Errorf("BytesSent = %f, want 1024", c.BytesSent.Get())
	}
}

func TestPrometheusFormat(t *testing.T) {
	c := NewCollector()
	c.UpdateFromSnapshot(5, 4, 0.8, 2)

	req := httptest.NewRequest("GET", "/metrics", nil)
	w := httptest.NewRecorder()
	c.ServeHTTP(w, req)

	body := w.Body.String()

	// Check Prometheus format
	if !strings.Contains(body, "# HELP mesh_peers_total") {
		t.Error("missing HELP for mesh_peers_total")
	}
	if !strings.Contains(body, "# TYPE mesh_peers_total gauge") {
		t.Error("missing TYPE for mesh_peers_total")
	}
	if !strings.Contains(body, "mesh_peers_total 5") {
		t.Error("missing value for mesh_peers_total")
	}
	if !strings.Contains(body, "mesh_pqc_sessions 2") {
		t.Error("missing value for mesh_pqc_sessions")
	}
}
