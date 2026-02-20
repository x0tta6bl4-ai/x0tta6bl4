// Package telemetry collects and reports system/mesh metrics.
package telemetry

import (
	"log/slog"
	"os"
	"runtime"
	"sync"
	"time"
)

// Metrics holds a snapshot of agent telemetry.
type Metrics struct {
	Timestamp time.Time `json:"timestamp"`

	// System
	CPUCount     int     `json:"cpu_count"`
	GoRoutines   int     `json:"goroutines"`
	HeapAllocMB  float64 `json:"heap_alloc_mb"`
	SysMemMB     float64 `json:"sys_mem_mb"`

	// Mesh
	PeersTotal   int     `json:"peers_total"`
	PeersHealthy int     `json:"peers_healthy"`
	MsgSent      int64   `json:"messages_sent"`
	MsgRecv      int64   `json:"messages_recv"`
	UptimeSec    float64 `json:"uptime_sec"`
	HealthScore  float64 `json:"health_score"`
}

// StatsSource provides mesh node statistics.
type StatsSource interface {
	GetStats() map[string]any
}

// Reporter collects metrics and makes them available for the API client.
type Reporter struct {
	mu      sync.RWMutex
	source  StatsSource
	latest  *Metrics
	history []Metrics
	maxHist int
	started time.Time
	logger  *slog.Logger
}

// NewReporter creates a new telemetry reporter.
func NewReporter(source StatsSource) *Reporter {
	return &Reporter{
		source:  source,
		history: make([]Metrics, 0, 60),
		maxHist: 60,
		started: time.Now(),
		logger:  slog.Default().With("component", "telemetry"),
	}
}

// Collect gathers current metrics.
func (r *Reporter) Collect() Metrics {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)

	hostname, _ := os.Hostname()
	_ = hostname

	m := Metrics{
		Timestamp:   time.Now(),
		CPUCount:    runtime.NumCPU(),
		GoRoutines:  runtime.NumGoroutine(),
		HeapAllocMB: float64(memStats.HeapAlloc) / 1024 / 1024,
		SysMemMB:    float64(memStats.Sys) / 1024 / 1024,
		UptimeSec:   time.Since(r.started).Seconds(),
	}

	// Get mesh stats
	if r.source != nil {
		stats := r.source.GetStats()
		if v, ok := stats["peers_total"].(int); ok {
			m.PeersTotal = v
		}
		if v, ok := stats["peers_healthy"].(int); ok {
			m.PeersHealthy = v
		}
		if v, ok := stats["messages_sent"].(int64); ok {
			m.MsgSent = v
		}
		if v, ok := stats["messages_recv"].(int64); ok {
			m.MsgRecv = v
		}
		if v, ok := stats["health_score"].(float64); ok {
			m.HealthScore = v
		}
	}

	r.mu.Lock()
	r.latest = &m
	if len(r.history) >= r.maxHist {
		r.history = r.history[1:]
	}
	r.history = append(r.history, m)
	r.mu.Unlock()

	return m
}

// Latest returns the last collected metrics.
func (r *Reporter) Latest() *Metrics {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if r.latest == nil {
		return nil
	}
	m := *r.latest
	return &m
}

// History returns historical metrics.
func (r *Reporter) History() []Metrics {
	r.mu.RLock()
	defer r.mu.RUnlock()
	result := make([]Metrics, len(r.history))
	copy(result, r.history)
	return result
}
