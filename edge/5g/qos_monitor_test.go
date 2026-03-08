package edge5g

import "testing"

func TestEstimateLatencyMsFromStatsFallbackOnZeroTotal(t *testing.T) {
	if got := estimateLatencyMsFromStats(BPFStats{}); got != 25 {
		t.Fatalf("expected fallback latency 25, got %d", got)
	}
}

func TestEstimateLatencyMsFromStatsUsesDropRatioHeuristic(t *testing.T) {
	stats := BPFStats{Total: 1000, Dropped: 50}
	if got := estimateLatencyMsFromStats(stats); got != 20 {
		t.Fatalf("expected heuristic latency 20, got %d", got)
	}
}

func TestEBPFQoSMonitorEstimatedLatencyFallsBackWhenStatsUnavailable(t *testing.T) {
	monitor := &EBPFQoSMonitor{}
	if got := monitor.GetEstimatedLatencyMs("ue1"); got != 25 {
		t.Fatalf("expected fallback latency 25, got %d", got)
	}
}

func TestMockQoSMonitorProvidesStableBaseline(t *testing.T) {
	monitor := &MockQoSMonitor{}
	if got := monitor.GetEstimatedLatencyMs("ue1"); got != 25 {
		t.Fatalf("expected mock latency 25, got %d", got)
	}
}
