package healing

import (
	"context"
	"testing"
	"time"
)

func TestRuleBasedDetector(t *testing.T) {
	d := NewRuleBasedDetector()

	tests := []struct {
		name      string
		obs       Observation
		wantScore float64
	}{
		{
			name:      "healthy_mesh",
			obs:       Observation{PeerCount: 10, HealthyPeers: 10, AvgLatencyMs: 10, PacketLoss: 0},
			wantScore: 0.0,
		},
		{
			name:      "no_peers",
			obs:       Observation{PeerCount: 0, HealthyPeers: 0},
			wantScore: 0.4,
		},
		{
			name:      "half_unhealthy",
			obs:       Observation{PeerCount: 10, HealthyPeers: 5, AvgLatencyMs: 10, PacketLoss: 0},
			wantScore: 0.15,
		},
		{
			name:      "high_latency",
			obs:       Observation{PeerCount: 10, HealthyPeers: 10, AvgLatencyMs: 600, PacketLoss: 0},
			wantScore: 0.2,
		},
		{
			name:      "high_packet_loss",
			obs:       Observation{PeerCount: 10, HealthyPeers: 10, AvgLatencyMs: 10, PacketLoss: 0.1},
			wantScore: 0.1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			score := d.AnalyzeScore(tt.obs)
			diff := score - tt.wantScore
			if diff < -0.01 || diff > 0.01 {
				t.Errorf("AnalyzeScore() = %f, want %f (±0.01)", score, tt.wantScore)
			}
		})
	}
}

func TestHybridDetector_RulesOnly(t *testing.T) {
	// No ML detector — should use rules only
	detector := NewHybridAnomalyDetector(nil)

	obs := Observation{PeerCount: 10, HealthyPeers: 10, AvgLatencyMs: 10, PacketLoss: 0}
	score, isAnomaly, method := detector.Analyze(context.Background(), obs)

	if method != "rules" {
		t.Errorf("method = %s, want rules", method)
	}
	if isAnomaly {
		t.Errorf("isAnomaly = true for healthy mesh")
	}
	if score >= 0.5 {
		t.Errorf("score = %f, want < 0.5 for healthy mesh", score)
	}
}

func TestHybridDetector_MLDisabled(t *testing.T) {
	// ML detector disabled — should use rules
	ml := NewGraphSAGEDetector(GraphSAGEConfig{
		Enabled: false,
		Endpoint: "http://localhost:9999",
	})
	detector := NewHybridAnomalyDetector(ml)

	obs := Observation{PeerCount: 0, HealthyPeers: 0}
	score, _, method := detector.Analyze(context.Background(), obs)

	if method != "rules" {
		t.Errorf("method = %s, want rules (ML disabled)", method)
	}
	if score < 0.4 {
		t.Errorf("score = %f, want >= 0.4 for no peers", score)
	}
}

func TestGraphSAGEAnomalyRequest(t *testing.T) {
	obs := Observation{
		PeerCount:    5,
		HealthyPeers: 3,
		AvgLatencyMs: 250,
		PacketLoss:   0.02,
	}

	req := GraphSAGEAnomalyRequest{
		PeerCount:    obs.PeerCount,
		HealthyPeers: obs.HealthyPeers,
		AvgLatencyMs: obs.AvgLatencyMs,
		PacketLoss:   obs.PacketLoss,
	}

	if req.PeerCount != 5 {
		t.Errorf("PeerCount = %d, want 5", req.PeerCount)
	}
	if req.HealthyPeers != 3 {
		t.Errorf("HealthyPeers = %d, want 3", req.HealthyPeers)
	}
}

func TestGraphSAGEDetectorConfig(t *testing.T) {
	d := NewGraphSAGEDetector(GraphSAGEConfig{
		Enabled:          true,
		Endpoint:         "http://localhost:8080",
		AnomalyThreshold: 0.8,
	})

	if d.cfg.AnomalyThreshold != 0.8 {
		t.Errorf("AnomalyThreshold = %f, want 0.8", d.cfg.AnomalyThreshold)
	}
	if d.cfg.Timeout != 2*time.Second {
		t.Errorf("Timeout = %v, want 2s", d.cfg.Timeout)
	}
}
