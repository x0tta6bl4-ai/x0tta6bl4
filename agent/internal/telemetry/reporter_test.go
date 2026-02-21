package telemetry

import (
	"testing"
)

type mockSource struct {
	stats map[string]any
}

func (m *mockSource) GetStats() map[string]any {
	return m.stats
}

func TestNewReporter(t *testing.T) {
	r := NewReporter(nil)
	if r.latest != nil {
		t.Error("latest should be nil initially")
	}
	if len(r.History()) != 0 {
		t.Error("history should be empty initially")
	}
}

func TestCollect_BasicMetrics(t *testing.T) {
	r := NewReporter(nil)
	m := r.Collect()

	if m.CPUCount <= 0 {
		t.Error("CPUCount should be positive")
	}
	if m.GoRoutines <= 0 {
		t.Error("GoRoutines should be positive")
	}
	if m.UptimeSec <= 0 {
		t.Error("UptimeSec should be positive")
	}
	if m.HeapAllocMB <= 0 {
		t.Error("HeapAllocMB should be positive")
	}
}

func TestCollect_WithSource(t *testing.T) {
	src := &mockSource{stats: map[string]any{
		"peers_total":   5,
		"peers_healthy": 4,
		"messages_sent": int64(100),
		"messages_recv": int64(200),
		"health_score":  0.95,
	}}
	r := NewReporter(src)
	m := r.Collect()

	if m.PeersTotal != 5 {
		t.Errorf("PeersTotal = %d, want 5", m.PeersTotal)
	}
	if m.PeersHealthy != 4 {
		t.Errorf("PeersHealthy = %d, want 4", m.PeersHealthy)
	}
	if m.MsgSent != 100 {
		t.Errorf("MsgSent = %d, want 100", m.MsgSent)
	}
	if m.MsgRecv != 200 {
		t.Errorf("MsgRecv = %d, want 200", m.MsgRecv)
	}
	if m.HealthScore != 0.95 {
		t.Errorf("HealthScore = %f, want 0.95", m.HealthScore)
	}
}

func TestLatest_BeforeCollect(t *testing.T) {
	r := NewReporter(nil)
	if r.Latest() != nil {
		t.Error("Latest should return nil before first Collect")
	}
}

func TestLatest_AfterCollect(t *testing.T) {
	r := NewReporter(nil)
	r.Collect()
	m := r.Latest()
	if m == nil {
		t.Fatal("Latest should not be nil after Collect")
	}
	if m.CPUCount <= 0 {
		t.Error("latest CPUCount should be positive")
	}
}

func TestHistory_Accumulates(t *testing.T) {
	r := NewReporter(nil)
	for i := 0; i < 5; i++ {
		r.Collect()
	}
	h := r.History()
	if len(h) != 5 {
		t.Errorf("history length = %d, want 5", len(h))
	}
}

func TestHistory_MaxLimit(t *testing.T) {
	r := NewReporter(nil)
	r.maxHist = 3

	for i := 0; i < 10; i++ {
		r.Collect()
	}

	h := r.History()
	if len(h) != 3 {
		t.Errorf("history length = %d, want max 3", len(h))
	}
}

func TestHistory_ReturnsCopy(t *testing.T) {
	r := NewReporter(nil)
	r.Collect()

	h1 := r.History()
	h2 := r.History()

	// Modify h1 and check h2 is unaffected
	if len(h1) > 0 {
		h1[0].CPUCount = 999
	}
	if h2[0].CPUCount == 999 {
		t.Error("History should return a copy, not a reference")
	}
}
