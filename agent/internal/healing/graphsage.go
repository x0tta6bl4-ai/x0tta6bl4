// Package healing implements MAPE-K self-healing with optional ML-based
// anomaly detection via GraphSAGE mesh topology analysis.
package healing

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"net/http"
	"strings"
	"sync"
	"time"
)

// GraphSAGEConfig configures the GraphSAGE anomaly detector.
type GraphSAGEConfig struct {
	// Endpoint is the GraphSAGE inference service URL.
	Endpoint string
	// AnomalyThreshold is the score above which a node is considered anomalous (0.0-1.0).
	AnomalyThreshold float64
	// Timeout for inference requests.
	Timeout time.Duration
	// Enabled toggles ML-based detection (falls back to rules if disabled).
	Enabled bool
}

// GraphSAGEAnomalyRequest is the payload sent to the inference service.
type GraphSAGEAnomalyRequest struct {
	NodeID       string             `json:"node_id"`
	PeerCount    int                `json:"peer_count"`
	HealthyPeers int                `json:"healthy_peers"`
	AvgLatencyMs float64            `json:"avg_latency_ms"`
	PacketLoss   float64            `json:"packet_loss"`
	MsgSent      int64              `json:"msg_sent"`
	MsgRecv      int64              `json:"msg_recv"`
	UptimeSec    float64            `json:"uptime_sec"`
	Features     map[string]float64 `json:"features,omitempty"`
}

// GraphSAGEAnomalyResponse is the inference result.
type GraphSAGEAnomalyResponse struct {
	AnomalyScore float64 `json:"anomaly_score"`
	IsAnomaly    bool    `json:"is_anomaly"`
	AnomalyType  string  `json:"anomaly_type,omitempty"`
	Confidence   float64 `json:"confidence"`
}

// GraphSAGEDetector wraps a remote GraphSAGE service for anomaly detection.
type GraphSAGEDetector struct {
	cfg    GraphSAGEConfig
	client *http.Client
	logger *slog.Logger

	mu             sync.RWMutex
	lastScore      float64
	lastAnomaly    bool
	totalRequests  uint64
	failedRequests uint64
}

// NewGraphSAGEDetector creates a new GraphSAGE anomaly detector.
func NewGraphSAGEDetector(cfg GraphSAGEConfig) *GraphSAGEDetector {
	if cfg.Timeout == 0 {
		cfg.Timeout = 2 * time.Second
	}
	if cfg.AnomalyThreshold == 0 {
		cfg.AnomalyThreshold = 0.7
	}
	return &GraphSAGEDetector{
		cfg: cfg,
		client: &http.Client{
			Timeout: cfg.Timeout,
		},
		logger: slog.Default().With("component", "graphsage-detector"),
	}
}

// DetectAnomaly scores the current observation using GraphSAGE.
func (d *GraphSAGEDetector) DetectAnomaly(ctx context.Context, obs Observation) (float64, bool, error) {
	if !d.cfg.Enabled {
		return 0, false, nil
	}

	req := GraphSAGEAnomalyRequest{
		PeerCount:    obs.PeerCount,
		HealthyPeers: obs.HealthyPeers,
		AvgLatencyMs: obs.AvgLatencyMs,
		PacketLoss:   obs.PacketLoss,
	}

	body, err := json.Marshal(req)
	if err != nil {
		return 0, false, fmt.Errorf("marshal request: %w", err)
	}

	url := d.cfg.Endpoint + "/api/v1/anomaly/detect"
	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, strings.NewReader(string(body)))
	if err != nil {
		return 0, false, fmt.Errorf("create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := d.client.Do(httpReq)
	if err != nil {
		d.mu.Lock()
		d.failedRequests++
		d.mu.Unlock()
		return 0, false, fmt.Errorf("inference request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, false, fmt.Errorf("inference returned HTTP %d", resp.StatusCode)
	}

	var result GraphSAGEAnomalyResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, false, fmt.Errorf("decode response: %w", err)
	}

	d.mu.Lock()
	d.lastScore = result.AnomalyScore
	d.lastAnomaly = result.IsAnomaly
	d.totalRequests++
	d.mu.Unlock()

	return result.AnomalyScore, result.IsAnomaly, nil
}

// GetStats returns detector statistics.
func (d *GraphSAGEDetector) GetStats() (lastScore float64, lastAnomaly bool, total, failed uint64) {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return d.lastScore, d.lastAnomaly, d.totalRequests, d.failedRequests
}

// HybridAnomalyDetector combines rule-based and ML-based detection.
// Falls back to rules when GraphSAGE is unavailable or fails.
type HybridAnomalyDetector struct {
	rules  *RuleBasedDetector
	ml     *GraphSAGEDetector
	logger *slog.Logger
}

// RuleBasedDetector is the existing rule-based analysis.
type RuleBasedDetector struct {
	latencyThreshold  float64
	packetLossThreshold float64
	peerLossThreshold float64
}

// NewRuleBasedDetector creates a rule-based detector.
func NewRuleBasedDetector() *RuleBasedDetector {
	return &RuleBasedDetector{
		latencyThreshold:    LatencyThresholdMs,
		packetLossThreshold: PacketLossThreshold,
		peerLossThreshold:   PeerLossThreshold,
	}
}

// AnalyzeScore returns a combined anomaly score [0.0, 1.0] based on rules.
func (r *RuleBasedDetector) AnalyzeScore(obs Observation) float64 {
	score := 0.0

	// Peer loss scoring
	if obs.PeerCount == 0 {
		score += 0.4
	} else if obs.PeerCount > 0 {
		unhealthyRatio := 1.0 - float64(obs.HealthyPeers)/float64(obs.PeerCount)
		score += unhealthyRatio * 0.3
	}

	// Latency scoring (normalized to [0, 1])
	if obs.AvgLatencyMs > 0 {
		latencyScore := math.Min(obs.AvgLatencyMs/r.latencyThreshold, 1.0)
		score += latencyScore * 0.2
	}

	// Packet loss scoring
	if obs.PacketLoss > 0 {
		lossScore := math.Min(obs.PacketLoss/r.packetLossThreshold, 1.0)
		score += lossScore * 0.1
	}

	return math.Min(score, 1.0)
}

// NewHybridAnomalyDetector creates a hybrid detector with both rules and ML.
func NewHybridAnomalyDetector(ml *GraphSAGEDetector) *HybridAnomalyDetector {
	return &HybridAnomalyDetector{
		rules:  NewRuleBasedDetector(),
		ml:     ml,
		logger: slog.Default().With("component", "hybrid-detector"),
	}
}

// Analyze performs hybrid anomaly detection.
// Returns: score [0.0, 1.0], isAnomaly, method used ("ml" or "rules").
func (h *HybridAnomalyDetector) Analyze(ctx context.Context, obs Observation) (float64, bool, string) {
	// Always compute rule-based score as fallback
	ruleScore := h.rules.AnalyzeScore(obs)
	isAnomaly := ruleScore > 0.5
	method := "rules"

	// Try ML-based detection if available
	if h.ml != nil && h.ml.cfg.Enabled {
		mlScore, mlAnomaly, err := h.ml.DetectAnomaly(ctx, obs)
		if err == nil {
			// Weighted average: 60% ML, 40% rules
			combinedScore := 0.6*mlScore + 0.4*ruleScore
			isAnomaly = combinedScore > 0.5 || mlAnomaly
			method = "ml+rules"
			h.logger.Debug("hybrid anomaly score",
				"ml", mlScore, "rules", ruleScore, "combined", combinedScore)
			return combinedScore, isAnomaly, method
		}
		h.logger.Warn("ML detection failed, falling back to rules", "error", err)
	}

	return ruleScore, isAnomaly, method
}
