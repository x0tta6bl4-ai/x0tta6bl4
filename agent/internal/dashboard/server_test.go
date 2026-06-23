package dashboard

import (
	"encoding/json"
	"net/http/httptest"
	"testing"
	"time"
)

func TestDashboardAPI(t *testing.T) {
	// Create mock provider
	provider := NewSnapshotProvider()
	provider.Update(MeshSnapshot{
		Timestamp: time.Now(),
		NodeID:    "test-node",
		State:     "active",
		Peers: []PeerInfo{
			{NodeID: "peer-1", Addr: "10.0.0.1:5000", Healthy: true, PQCSession: true},
			{NodeID: "peer-2", Addr: "10.0.0.2:5000", Healthy: false, PQCSession: false},
		},
		Healing: HealingInfo{Running: true, TotalEvents: 5},
		PQC:     PQCInfo{ActiveSessions: 1, Algorithm: "ML-KEM-768"},
		Metrics: MetricsInfo{HealthScore: 0.75, UptimeSec: 3600},
	})

	server := NewServer(provider, 8080)

	tests := []struct {
		name     string
		path     string
		wantCode int
	}{
		{"snapshot", "/api/v1/mesh/snapshot", 200},
		{"peers", "/api/v1/mesh/peers", 200},
		{"healing", "/api/v1/mesh/healing", 200},
		{"pqc", "/api/v1/mesh/pqc", 200},
		{"metrics", "/api/v1/mesh/metrics", 200},
		{"health", "/api/v1/mesh/health", 200},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", tt.path, nil)
			w := httptest.NewRecorder()
			server.mux.ServeHTTP(w, req)

			if w.Code != tt.wantCode {
				t.Errorf("GET %s = %d, want %d", tt.path, w.Code, tt.wantCode)
			}

			// Verify JSON response
			if tt.wantCode == 200 && tt.name != "health" {
				var result interface{}
				if err := json.NewDecoder(w.Body).Decode(&result); err != nil {
					t.Errorf("decode response: %v", err)
				}
			}
		})
	}
}

func TestSnapshotProvider(t *testing.T) {
	provider := NewSnapshotProvider()

	// Empty snapshot
	snap := provider.GetSnapshot()
	if snap.NodeID != "" {
		t.Errorf("empty snapshot NodeID = %s, want empty", snap.NodeID)
	}
	if provider.PeerCount() != 0 {
		t.Errorf("PeerCount = %d, want 0", provider.PeerCount())
	}

	// Update
	provider.Update(MeshSnapshot{
		NodeID: "node-1",
		Peers:  []PeerInfo{{NodeID: "p1"}, {NodeID: "p2"}},
	})

	snap = provider.GetSnapshot()
	if snap.NodeID != "node-1" {
		t.Errorf("NodeID = %s, want node-1", snap.NodeID)
	}
	if provider.PeerCount() != 2 {
		t.Errorf("PeerCount = %d, want 2", provider.PeerCount())
	}
}
