// Package metrics provides Prometheus metrics export for the mesh agent.
// Exposes peer health, PQC sessions, healing events, and eBPF stats.
package metrics

import (
	"fmt"
	"log/slog"
	"net/http"
	"sync"
	"time"
)

// Gauge represents a single numeric value that can go up and down.
type Gauge struct {
	mu    sync.RWMutex
	value float64
	desc  string
}

func newGauge(desc string) *Gauge {
	return &Gauge{desc: desc}
}

func (g *Gauge) Set(v float64) {
	g.mu.Lock()
	g.value = v
	g.mu.Unlock()
}

func (g *Gauge) Inc() {
	g.mu.Lock()
	g.value++
	g.mu.Unlock()
}

func (g *Gauge) Dec() {
	g.mu.Lock()
	g.value--
	g.mu.Unlock()
}

func (g *Gauge) Get() float64 {
	g.mu.RLock()
	defer g.mu.RUnlock()
	return g.value
}

// Counter represents a monotonically increasing value.
type Counter struct {
	mu    sync.RWMutex
	value float64
	desc  string
}

func newCounter(desc string) *Counter {
	return &Counter{desc: desc}
}

func (c *Counter) Inc() {
	c.mu.Lock()
	c.value++
	c.mu.Unlock()
}

func (c *Counter) Add(v float64) {
	c.mu.Lock()
	c.value += v
	c.mu.Unlock()
}

func (c *Counter) Get() float64 {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.value
}

// Collector gathers all metrics for Prometheus export.
type Collector struct {
	// Peer metrics
	PeersTotal      *Gauge
	PeersHealthy    *Gauge
	PeersUnhealthy  *Gauge

	// PQC metrics
	PQCSessions     *Gauge
	PQCKeyHits      *Counter

	// Healing metrics
	HealingActions  *Counter
	HealingErrors   *Counter

	// Network metrics
	MessagesSent    *Counter
	MessagesRecv    *Counter
	BytesSent       *Counter
	BytesRecv       *Counter

	// eBPF metrics
	eBPFPacketsTotal   *Counter
	eBPFPacketsPassed  *Counter
	eBPFPacketsDropped *Counter

	// Health score
	HealthScore     *Gauge

	mu     sync.RWMutex
	logger *slog.Logger
}

// NewCollector creates a new metrics collector.
func NewCollector() *Collector {
	return &Collector{
		PeersTotal:      newGauge("Total number of known peers"),
		PeersHealthy:    newGauge("Number of healthy peers"),
		PeersUnhealthy:  newGauge("Number of unhealthy peers"),
		PQCSessions:     newGauge("Active PQC sessions"),
		PQCKeyHits:      newCounter("Total eBPF PQC key hits"),
		HealingActions:  newCounter("Total healing actions executed"),
		HealingErrors:   newCounter("Total healing action errors"),
		MessagesSent:    newCounter("Total messages sent"),
		MessagesRecv:    newCounter("Total messages received"),
		BytesSent:       newCounter("Total bytes sent"),
		BytesRecv:       newCounter("Total bytes received"),
		eBPFPacketsTotal:   newCounter("Total eBPF packets processed"),
		eBPFPacketsPassed:  newCounter("Total eBPF packets passed"),
		eBPFPacketsDropped: newCounter("Total eBPF packets dropped"),
		HealthScore:     newGauge("Node health score [0-1]"),
		logger:          slog.Default().With("component", "metrics"),
	}
}

// UpdateFromSnapshot refreshes all metrics from a mesh snapshot.
func (c *Collector) UpdateFromSnapshot(peersTotal, peersHealthy int, healthScore float64, pqcSessions int) {
	c.PeersTotal.Set(float64(peersTotal))
	c.PeersHealthy.Set(float64(peersHealthy))
	c.PeersUnhealthy.Set(float64(peersTotal - peersHealthy))
	c.HealthScore.Set(healthScore)
	c.PQCSessions.Set(float64(pqcSessions))
}

// RecordHealing increments healing counters.
func (c *Collector) RecordHealing(action string, success bool) {
	c.HealingActions.Inc()
	if !success {
		c.HealingErrors.Inc()
	}
}

// RecordMessage records a sent/received message.
func (c *Collector) RecordMessage(sent bool, bytes int64) {
	if sent {
		c.MessagesSent.Inc()
		c.BytesSent.Add(float64(bytes))
	} else {
		c.MessagesRecv.Inc()
		c.BytesRecv.Add(float64(bytes))
	}
}

// ServeHTTP implements http.Handler for Prometheus text format.
func (c *Collector) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")

	now := time.Now().Unix()
	c.writeGauge(w, "mesh_peers_total", "Total known peers", c.PeersTotal.Get(), now)
	c.writeGauge(w, "mesh_peers_healthy", "Healthy peers", c.PeersHealthy.Get(), now)
	c.writeGauge(w, "mesh_peers_unhealthy", "Unhealthy peers", c.PeersUnhealthy.Get(), now)
	c.writeGauge(w, "mesh_pqc_sessions", "Active PQC sessions", c.PQCSessions.Get(), now)
	c.writeGauge(w, "mesh_health_score", "Node health score", c.HealthScore.Get(), now)
	c.writeCounter(w, "mesh_pqc_key_hits_total", "eBPF PQC key hits", c.PQCKeyHits.Get(), now)
	c.writeCounter(w, "mesh_healing_actions_total", "Healing actions", c.HealingActions.Get(), now)
	c.writeCounter(w, "mesh_healing_errors_total", "Healing errors", c.HealingErrors.Get(), now)
	c.writeCounter(w, "mesh_messages_sent_total", "Messages sent", c.MessagesSent.Get(), now)
	c.writeCounter(w, "mesh_messages_recv_total", "Messages received", c.MessagesRecv.Get(), now)
	c.writeCounter(w, "mesh_bytes_sent_total", "Bytes sent", c.BytesSent.Get(), now)
	c.writeCounter(w, "mesh_bytes_recv_total", "Bytes received", c.BytesRecv.Get(), now)
	c.writeCounter(w, "mesh_ebpf_packets_total", "eBPF packets total", c.eBPFPacketsTotal.Get(), now)
	c.writeCounter(w, "mesh_ebpf_packets_passed", "eBPF packets passed", c.eBPFPacketsPassed.Get(), now)
	c.writeCounter(w, "mesh_ebpf_packets_dropped", "eBPF packets dropped", c.eBPFPacketsDropped.Get(), now)
}

func (c *Collector) writeGauge(w http.ResponseWriter, name, help string, value float64, ts int64) {
	fmt.Fprintf(w, "# HELP %s %s\n# TYPE %s gauge\n%s %g %d\n", name, help, name, name, value, ts)
}

func (c *Collector) writeCounter(w http.ResponseWriter, name, help string, value float64, ts int64) {
	fmt.Fprintf(w, "# HELP %s %s\n# TYPE %s counter\n%s %g %d\n", name, help, name, name, value, ts)
}

// MetricsServer is the HTTP server for Prometheus metrics.
type MetricsServer struct {
	collector *Collector
	mux       *http.ServeMux
	addr      string
	logger    *slog.Logger
}

// NewMetricsServer creates a new metrics HTTP server.
func NewMetricsServer(addr string) *MetricsServer {
	collector := NewCollector()
	mux := http.NewServeMux()
	mux.Handle("/metrics", collector)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})

	return &MetricsServer{
		collector: collector,
		mux:       mux,
		addr:      addr,
		logger:    slog.Default().With("component", "metrics-server"),
	}
}

// Collector returns the metrics collector.
func (s *MetricsServer) Collector() *Collector {
	return s.collector
}

// ListenAndServe starts the metrics server.
func (s *MetricsServer) ListenAndServe() error {
	s.logger.Info("metrics server starting", "addr", s.addr)
	return http.ListenAndServe(s.addr, s.mux)
}
