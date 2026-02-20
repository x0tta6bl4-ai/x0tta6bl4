// Package healing implements a lightweight MAPE-K self-healing loop.
// Monitor → Analyze → Plan → Execute → Knowledge
// No AI models — deterministic rules for latency, packet loss, peer health.
package healing

import (
	"log/slog"
	"sync"
	"time"
)

// Thresholds for anomaly detection.
const (
	LatencyThresholdMs   = 500.0
	PacketLossThreshold  = 0.05 // 5%
	PeerLossThreshold    = 0.5  // 50% of peers lost
	CheckInterval        = 10 * time.Second
)

// Action represents a healing action.
type Action int

const (
	ActionNone Action = iota
	ActionReroute
	ActionReconnect
	ActionRestartDiscovery
	ActionAlertControlPlane
)

func (a Action) String() string {
	switch a {
	case ActionReroute:
		return "reroute"
	case ActionReconnect:
		return "reconnect"
	case ActionRestartDiscovery:
		return "restart_discovery"
	case ActionAlertControlPlane:
		return "alert_control_plane"
	default:
		return "none"
	}
}

// Observation is a single monitoring data point.
type Observation struct {
	Timestamp    time.Time
	PeerCount    int
	HealthyPeers int
	AvgLatencyMs float64
	PacketLoss   float64
	State        string
}

// HealingEvent records an action taken by the MAPE-K loop.
type HealingEvent struct {
	Timestamp   time.Time
	Observation Observation
	Diagnosis   string
	Action      Action
	Success     bool
}

// StatsProvider supplies current node statistics.
type StatsProvider interface {
	GetStats() map[string]any
}

// ActionExecutor applies a healing action.
type ActionExecutor interface {
	ExecuteAction(action Action) error
}

// Monitor implements the MAPE-K self-healing loop.
type Monitor struct {
	mu sync.RWMutex

	statsProvider  StatsProvider
	executor       ActionExecutor

	observations []Observation
	events       []HealingEvent
	maxHistory   int

	running bool
	stopCh  chan struct{}
	logger  *slog.Logger

	// Baseline (learned from first N observations)
	baselinePeers int
}

// NewMonitor creates a new healing monitor.
func NewMonitor(sp StatsProvider, exec ActionExecutor) *Monitor {
	return &Monitor{
		statsProvider: sp,
		executor:      exec,
		observations:  make([]Observation, 0, 100),
		events:        make([]HealingEvent, 0, 50),
		maxHistory:    100,
		stopCh:        make(chan struct{}),
		logger:        slog.Default().With("component", "healing"),
	}
}

// Start begins the MAPE-K loop.
func (m *Monitor) Start() {
	m.running = true
	go m.loop()
	m.logger.Info("MAPE-K healing loop started", "interval", CheckInterval)
}

// Stop halts the MAPE-K loop.
func (m *Monitor) Stop() {
	m.running = false
	close(m.stopCh)
	m.logger.Info("MAPE-K healing loop stopped")
}

// GetEvents returns the history of healing events.
func (m *Monitor) GetEvents() []HealingEvent {
	m.mu.RLock()
	defer m.mu.RUnlock()
	result := make([]HealingEvent, len(m.events))
	copy(result, m.events)
	return result
}

// GetLatestObservation returns the most recent observation.
func (m *Monitor) GetLatestObservation() *Observation {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if len(m.observations) == 0 {
		return nil
	}
	obs := m.observations[len(m.observations)-1]
	return &obs
}

func (m *Monitor) loop() {
	ticker := time.NewTicker(CheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			m.cycle()
		case <-m.stopCh:
			return
		}
	}
}

func (m *Monitor) cycle() {
	// M — Monitor
	obs := m.monitor()

	// A — Analyze
	diagnosis, action := m.analyze(obs)

	// P — Plan (implicit in analyze for lightweight version)

	// E — Execute
	success := true
	if action != ActionNone {
		if m.executor != nil {
			if err := m.executor.ExecuteAction(action); err != nil {
				m.logger.Error("healing action failed", "action", action, "error", err)
				success = false
			} else {
				m.logger.Info("healing action executed", "action", action, "diagnosis", diagnosis)
			}
		}
	}

	// K — Knowledge
	m.mu.Lock()
	if len(m.observations) >= m.maxHistory {
		m.observations = m.observations[1:]
	}
	m.observations = append(m.observations, obs)

	if action != ActionNone {
		if len(m.events) >= m.maxHistory {
			m.events = m.events[1:]
		}
		m.events = append(m.events, HealingEvent{
			Timestamp:   time.Now(),
			Observation: obs,
			Diagnosis:   diagnosis,
			Action:      action,
			Success:     success,
		})
	}

	// Update baseline
	if m.baselinePeers == 0 && obs.PeerCount > 0 {
		m.baselinePeers = obs.PeerCount
	}
	m.mu.Unlock()
}

func (m *Monitor) monitor() Observation {
	stats := m.statsProvider.GetStats()

	peersTotal, _ := stats["peers_total"].(int)
	peersHealthy, _ := stats["peers_healthy"].(int)
	state, _ := stats["state"].(string)

	return Observation{
		Timestamp:    time.Now(),
		PeerCount:    peersTotal,
		HealthyPeers: peersHealthy,
		State:        state,
	}
}

func (m *Monitor) analyze(obs Observation) (string, Action) {
	// Rule 1: No peers at all — restart discovery
	if obs.PeerCount == 0 {
		return "no peers detected", ActionRestartDiscovery
	}

	// Rule 2: Significant peer loss — alert + reconnect
	m.mu.RLock()
	baseline := m.baselinePeers
	m.mu.RUnlock()

	if baseline > 0 {
		lossRatio := 1.0 - float64(obs.PeerCount)/float64(baseline)
		if lossRatio > PeerLossThreshold {
			return "significant peer loss", ActionReconnect
		}
	}

	// Rule 3: Many unhealthy peers — reroute traffic
	if obs.PeerCount > 0 {
		unhealthyRatio := 1.0 - float64(obs.HealthyPeers)/float64(obs.PeerCount)
		if unhealthyRatio > 0.5 {
			return "majority of peers unhealthy", ActionReroute
		}
	}

	// Rule 4: High latency
	if obs.AvgLatencyMs > LatencyThresholdMs {
		return "high latency detected", ActionReroute
	}

	// Rule 5: High packet loss
	if obs.PacketLoss > PacketLossThreshold {
		return "high packet loss", ActionReroute
	}

	return "", ActionNone
}
