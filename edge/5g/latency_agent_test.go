package edge5g

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestLatencyAgentReport(t *testing.T) {
	// 1. Setup Mock Server
	var receivedRequest NodeHeartbeatRequest
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST request, got %s", r.Method)
		}
		if err := json.NewDecoder(r.Body).Decode(&receivedRequest); err != nil {
			t.Errorf("failed to decode request: %v", err)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	// 2. Setup Monitor Mock
	monitor := &MockQoSMonitor{}

	// 3. Setup Agent
	agent := NewLatencyAgent("test-node", "test-mesh", server.URL, monitor)
	
	// 4. Trigger Report
	agent.report(time.Now().Add(-10 * time.Minute))

	// 5. Verify Results
	if receivedRequest.NodeID != "test-node" {
		t.Errorf("expected node-id test-node, got %s", receivedRequest.NodeID)
	}
	
	latency, ok := receivedRequest.CustomMetrics["latency_ms"].(float64)
	if !ok || int64(latency) != 25 {
		t.Errorf("expected latency 25ms in custom metrics, got %v", receivedRequest.CustomMetrics["latency_ms"])
	}
	
	if receivedRequest.Uptime < 600 {
		t.Errorf("expected uptime around 600s, got %f", receivedRequest.Uptime)
	}
}
