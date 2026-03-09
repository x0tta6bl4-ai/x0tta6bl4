package edge5g

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"time"
)

// NodeHeartbeatRequest mirrors the MaaS API Pydantic model.
type NodeHeartbeatRequest struct {
	NodeID           string                 `json:"node_id"`
	MeshID           string                 `json:"mesh_id"`
	CPUUsage         float64                `json:"cpu_usage"`
	MemoryUsage      float64                `json:"memory_usage"`
	NeighborsCount   int                    `json:"neighbors_count"`
	RoutingTableSize int                    `json:"routing_table_size"`
	Uptime           float64                `json:"uptime"`
	CustomMetrics    map[string]interface{} `json:"custom_metrics"`
}

// LatencyAgent periodically reports telemetry and measured latency to MaaS API.
type LatencyAgent struct {
	NodeID     string
	MeshID     string
	ApiURL     string
	Monitor    QoSMonitor
	Interval   time.Duration
	HttpClient *http.Client
}

func NewLatencyAgent(nodeID, meshID, apiURL string, monitor QoSMonitor) *LatencyAgent {
	return &LatencyAgent{
		NodeID:     nodeID,
		MeshID:     meshID,
		ApiURL:     apiURL,
		Monitor:    monitor,
		Interval:   30 * time.Second,
		HttpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

func (a *LatencyAgent) Run() {
	log.Printf("🚀 Latency Agent started for node %s (Mesh: %s)", a.NodeID, a.MeshID)
	ticker := time.NewTicker(a.Interval)
	defer ticker.Stop()

	startTime := time.Now()

	for {
		select {
		case <-ticker.C:
			a.report(startTime)
		}
	}
}

func (a *LatencyAgent) report(startTime time.Time) {
	latencyMs := a.Monitor.GetEstimatedLatencyMs(a.NodeID)
	stats, _ := a.Monitor.GetPacketStats()

	req := NodeHeartbeatRequest{
		NodeID:           a.NodeID,
		MeshID:           a.MeshID,
		CPUUsage:         0.0, // Should be fetched from sys
		MemoryUsage:      0.0, // Should be fetched from sys
		NeighborsCount:   int(stats.Forwarded), // Simulated
		RoutingTableSize: 1,
		Uptime:           time.Since(startTime).Seconds(),
		CustomMetrics: map[string]interface{}{
			"latency_ms":   latencyMs,
			"total_pkts":   stats.Total,
			"dropped_pkts": stats.Dropped,
		},
	}

	payload, err := json.Marshal(req)
	if err != nil {
		log.Printf("❌ Error marshaling heartbeat: %v", err)
		return
	}

	resp, err := a.HttpClient.Post(a.ApiURL, "application/json", bytes.NewReader(payload))
	if err != nil {
		log.Printf("⚠️ Failed to send heartbeat to %s: %v", a.ApiURL, err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("⚠️ Heartbeat rejected: status %d", resp.StatusCode)
	} else {
		log.Printf("✅ Heartbeat sent: Latency=%dms", latencyMs)
	}
}
