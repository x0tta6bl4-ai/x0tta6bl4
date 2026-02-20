package healing

import (
	"fmt"
	"testing"
)

// mockStats implements StatsProvider for testing.
type mockStats struct {
	peersTotal   int
	peersHealthy int
	state        string
}

func (m *mockStats) GetStats() map[string]any {
	return map[string]any{
		"peers_total":   m.peersTotal,
		"peers_healthy": m.peersHealthy,
		"state":         m.state,
	}
}

// mockExecutor records actions for testing.
type mockExecutor struct {
	actions []Action
	fail    bool
}

func (m *mockExecutor) ExecuteAction(action Action) error {
	m.actions = append(m.actions, action)
	if m.fail {
		return fmt.Errorf("executor failed")
	}
	return nil
}

func TestAnalyze_NoPeers(t *testing.T) {
	stats := &mockStats{peersTotal: 0}
	mon := NewMonitor(stats, nil)

	obs := mon.monitor()
	diagnosis, action := mon.analyze(obs)

	if action != ActionRestartDiscovery {
		t.Errorf("action = %v, want ActionRestartDiscovery", action)
	}
	if diagnosis != "no peers detected" {
		t.Errorf("diagnosis = %s", diagnosis)
	}
}

func TestAnalyze_HealthyMesh(t *testing.T) {
	stats := &mockStats{peersTotal: 10, peersHealthy: 10}
	mon := NewMonitor(stats, nil)

	obs := mon.monitor()
	_, action := mon.analyze(obs)

	if action != ActionNone {
		t.Errorf("healthy mesh should have no action, got %v", action)
	}
}

func TestAnalyze_MajorityUnhealthy(t *testing.T) {
	stats := &mockStats{peersTotal: 10, peersHealthy: 3}
	mon := NewMonitor(stats, nil)

	obs := mon.monitor()
	diagnosis, action := mon.analyze(obs)

	if action != ActionReroute {
		t.Errorf("action = %v, want ActionReroute", action)
	}
	if diagnosis != "majority of peers unhealthy" {
		t.Errorf("diagnosis = %s", diagnosis)
	}
}

func TestAnalyze_PeerLoss(t *testing.T) {
	stats := &mockStats{peersTotal: 10, peersHealthy: 10}
	mon := NewMonitor(stats, nil)
	// Set baseline
	mon.baselinePeers = 10

	// Now simulate 60% loss
	stats.peersTotal = 4
	stats.peersHealthy = 4
	obs := mon.monitor()
	diagnosis, action := mon.analyze(obs)

	if action != ActionReconnect {
		t.Errorf("action = %v, want ActionReconnect", action)
	}
	if diagnosis != "significant peer loss" {
		t.Errorf("diagnosis = %s", diagnosis)
	}
}

func TestAnalyze_HighLatency(t *testing.T) {
	stats := &mockStats{peersTotal: 5, peersHealthy: 5}
	mon := NewMonitor(stats, nil)

	obs := Observation{PeerCount: 5, HealthyPeers: 5, AvgLatencyMs: 600}
	_, action := mon.analyze(obs)

	if action != ActionReroute {
		t.Errorf("action = %v, want ActionReroute for high latency", action)
	}
}

func TestAnalyze_HighPacketLoss(t *testing.T) {
	stats := &mockStats{peersTotal: 5, peersHealthy: 5}
	mon := NewMonitor(stats, nil)

	obs := Observation{PeerCount: 5, HealthyPeers: 5, PacketLoss: 0.1}
	_, action := mon.analyze(obs)

	if action != ActionReroute {
		t.Errorf("action = %v, want ActionReroute for packet loss", action)
	}
}

func TestCycle_ExecutesAction(t *testing.T) {
	stats := &mockStats{peersTotal: 0}
	exec := &mockExecutor{}
	mon := NewMonitor(stats, exec)

	mon.cycle()

	if len(exec.actions) != 1 {
		t.Fatalf("expected 1 action, got %d", len(exec.actions))
	}
	if exec.actions[0] != ActionRestartDiscovery {
		t.Errorf("action = %v, want ActionRestartDiscovery", exec.actions[0])
	}

	events := mon.GetEvents()
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
	if !events[0].Success {
		t.Error("event should be successful")
	}
}

func TestCycle_ExecutorFails(t *testing.T) {
	stats := &mockStats{peersTotal: 0}
	exec := &mockExecutor{fail: true}
	mon := NewMonitor(stats, exec)

	mon.cycle()

	events := mon.GetEvents()
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
	if events[0].Success {
		t.Error("event should be marked as failed")
	}
}

func TestGetLatestObservation_Empty(t *testing.T) {
	stats := &mockStats{peersTotal: 5, peersHealthy: 5}
	mon := NewMonitor(stats, nil)

	if obs := mon.GetLatestObservation(); obs != nil {
		t.Error("expected nil for empty observations")
	}
}

func TestGetLatestObservation_AfterCycle(t *testing.T) {
	stats := &mockStats{peersTotal: 5, peersHealthy: 5, state: "running"}
	mon := NewMonitor(stats, nil)

	mon.cycle()

	obs := mon.GetLatestObservation()
	if obs == nil {
		t.Fatal("expected observation")
	}
	if obs.PeerCount != 5 {
		t.Errorf("PeerCount = %d, want 5", obs.PeerCount)
	}
	if obs.State != "running" {
		t.Errorf("State = %s, want running", obs.State)
	}
}

func TestActionString(t *testing.T) {
	tests := []struct {
		action Action
		want   string
	}{
		{ActionNone, "none"},
		{ActionReroute, "reroute"},
		{ActionReconnect, "reconnect"},
		{ActionRestartDiscovery, "restart_discovery"},
		{ActionAlertControlPlane, "alert_control_plane"},
	}
	for _, tt := range tests {
		if got := tt.action.String(); got != tt.want {
			t.Errorf("%d.String() = %s, want %s", tt.action, got, tt.want)
		}
	}
}

func TestBaselineAutoLearn(t *testing.T) {
	stats := &mockStats{peersTotal: 8, peersHealthy: 8}
	mon := NewMonitor(stats, nil)

	if mon.baselinePeers != 0 {
		t.Error("baseline should start at 0")
	}

	mon.cycle()

	if mon.baselinePeers != 8 {
		t.Errorf("baseline = %d, want 8", mon.baselinePeers)
	}
}
