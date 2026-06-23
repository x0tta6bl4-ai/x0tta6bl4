// Package dashboard provides an HTTP server for mesh network visualization.
// Exposes REST API endpoints for real-time mesh topology, node health, and metrics.
package dashboard

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"sync"
	"time"
)

// MeshSnapshot is the current state of the mesh network.
type MeshSnapshot struct {
	Timestamp   time.Time      `json:"timestamp"`
	NodeID      string         `json:"node_id"`
	State       string         `json:"state"`
	Peers       []PeerInfo     `json:"peers"`
	Healing     HealingInfo    `json:"healing"`
	PQC         PQCInfo        `json:"pqc"`
	Metrics     MetricsInfo    `json:"metrics"`
}

// PeerInfo describes a connected peer.
type PeerInfo struct {
	NodeID     string  `json:"node_id"`
	Addr       string  `json:"addr"`
	Healthy    bool    `json:"healthy"`
	LatencyMs  float64 `json:"latency_ms"`
	BytesSent  int64   `json:"bytes_sent"`
	BytesRecv  int64   `json:"bytes_recv"`
	LastSeen   string  `json:"last_seen"`
	PQCSession bool    `json:"pqc_session"`
}

// HealingInfo describes the MAPE-K healing state.
type HealingInfo struct {
	Running     bool           `json:"running"`
	TotalEvents int            `json:"total_events"`
	Events      []HealingEvent `json:"events"`
}

// HealingEvent is a recorded healing action.
type HealingEvent struct {
	Timestamp string `json:"timestamp"`
	Action    string `json:"action"`
	Diagnosis string `json:"diagnosis"`
	Success   bool   `json:"success"`
}

// PQCInfo describes PQC tunnel state.
type PQCInfo struct {
	ActiveSessions int    `json:"active_sessions"`
	Algorithm      string `json:"algorithm"`
	TrustDomain    string `json:"trust_domain"`
}

// MetricsInfo contains aggregate metrics.
type MetricsInfo struct {
	MessagesSent   int64   `json:"messages_sent"`
	MessagesRecv   int64   `json:"messages_recv"`
	HealthScore    float64 `json:"health_score"`
	UptimeSec      float64 `json:"uptime_sec"`
	PacketsTotal   uint64  `json:"packets_total"`
	PacketsPassed  uint64  `json:"packets_passed"`
	PacketsDropped uint64  `json:"packets_dropped"`
	KeyHits        uint64  `json:"key_hits"`
}

// DataProvider supplies mesh data to the dashboard.
type DataProvider interface {
	GetSnapshot() MeshSnapshot
}

// Server is the dashboard HTTP server.
type Server struct {
	mux      *http.ServeMux
	provider DataProvider
	logger   *slog.Logger
}

// NewServer creates a new dashboard server.
func NewServer(provider DataProvider, port int) *Server {
	s := &Server{
		mux:      http.NewServeMux(),
		provider: provider,
		logger:   slog.Default().With("component", "dashboard"),
	}

	s.mux.HandleFunc("/api/v1/mesh/snapshot", s.handleSnapshot)
	s.mux.HandleFunc("/api/v1/mesh/peers", s.handlePeers)
	s.mux.HandleFunc("/api/v1/mesh/healing", s.handleHealing)
	s.mux.HandleFunc("/api/v1/mesh/pqc", s.handlePQC)
	s.mux.HandleFunc("/api/v1/mesh/metrics", s.handleMetrics)
	s.mux.HandleFunc("/api/v1/mesh/health", s.handleHealth)
	s.mux.Handle("/", http.FileServer(http.Dir("internal/dashboard/static")))

	return s
}

// ListenAndServe starts the server.
func (s *Server) ListenAndServe(addr string) error {
	s.logger.Info("dashboard server starting", "addr", addr)
	return http.ListenAndServe(addr, s.mux)
}

func (s *Server) handleSnapshot(w http.ResponseWriter, r *http.Request) {
	s.writeJSON(w, s.provider.GetSnapshot())
}

func (s *Server) handlePeers(w http.ResponseWriter, r *http.Request) {
	snap := s.provider.GetSnapshot()
	s.writeJSON(w, snap.Peers)
}

func (s *Server) handleHealing(w http.ResponseWriter, r *http.Request) {
	snap := s.provider.GetSnapshot()
	s.writeJSON(w, snap.Healing)
}

func (s *Server) handlePQC(w http.ResponseWriter, r *http.Request) {
	snap := s.provider.GetSnapshot()
	s.writeJSON(w, snap.PQC)
}

func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	snap := s.provider.GetSnapshot()
	s.writeJSON(w, snap.Metrics)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	s.writeJSON(w, map[string]string{"status": "ok"})
}

func (s *Server) writeJSON(w http.ResponseWriter, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(v)
}

// SnapshotProvider implements DataProvider using a callback.
type SnapshotProvider struct {
	mu       sync.RWMutex
	snapshot MeshSnapshot
	logger   *slog.Logger
}

// NewSnapshotProvider creates a new snapshot provider.
func NewSnapshotProvider() *SnapshotProvider {
	return &SnapshotProvider{
		logger: slog.Default().With("component", "snapshot-provider"),
	}
}

// Update refreshes the snapshot.
func (p *SnapshotProvider) Update(snap MeshSnapshot) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.snapshot = snap
}

// GetSnapshot returns the current snapshot.
func (p *SnapshotProvider) GetSnapshot() MeshSnapshot {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.snapshot
}

// PeerCount returns the number of connected peers.
func (p *SnapshotProvider) PeerCount() int {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return len(p.snapshot.Peers)
}
