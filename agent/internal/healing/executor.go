package healing

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"
)

// PeerEntry is a minimal peer health view for healing decisions.
type PeerEntry struct {
	NodeID  string
	Healthy bool
}

// DiscoveryRestarter can stop and restart peer discovery.
type DiscoveryRestarter interface {
	RestartDiscovery() error
}

// PeerRemover can evict a specific peer from the mesh.
type PeerRemover interface {
	RemovePeer(nodeID string)
}

// ControlPlaneAlerter sends alerts to the control plane API.
type ControlPlaneAlerter interface {
	SendHealingAlert(ctx context.Context, nodeID, diagnosis, action string) error
}

// MeshHealingExecutor implements ActionExecutor for the mesh agent.
// It wires MAPE-K healing actions to concrete mesh operations:
//   - ActionReroute: evict unhealthy peers
//   - ActionReconnect: evict unhealthy + restart discovery
//   - ActionRestartDiscovery: restart discovery only
//   - ActionAlertControlPlane: send alert via API
type MeshHealingExecutor struct {
	remover   PeerRemover
	restarter DiscoveryRestarter
	alerter   ControlPlaneAlerter
	peerFn    func() []PeerEntry // closure over mesh.Node.GetPeers
	nodeID    string
	logger    *slog.Logger

	mu             sync.Mutex
	lastActionTime time.Time
	actionCooldown time.Duration
}

// NewMeshHealingExecutor creates an executor wired to real mesh components.
// peerFn is a closure that returns the current peer list (avoids circular imports).
func NewMeshHealingExecutor(
	nodeID string,
	remover PeerRemover,
	restarter DiscoveryRestarter,
	alerter ControlPlaneAlerter,
	peerFn func() []PeerEntry,
) *MeshHealingExecutor {
	return &MeshHealingExecutor{
		nodeID:    nodeID,
		remover:   remover,
		restarter: restarter,
		alerter:   alerter,
		peerFn:    peerFn,
		logger:    slog.Default().With("component", "healing-executor"),
		// Minimum 30s between actions to prevent healing storms.
		actionCooldown: 30 * time.Second,
	}
}

// ExecuteAction dispatches a healing action to the mesh subsystem.
func (e *MeshHealingExecutor) ExecuteAction(action Action) error {
	e.mu.Lock()
	if time.Since(e.lastActionTime) < e.actionCooldown {
		e.mu.Unlock()
		e.logger.Debug("healing action skipped (cooldown)", "action", action)
		return nil
	}
	e.lastActionTime = time.Now()
	e.mu.Unlock()

	switch action {
	case ActionReroute:
		return e.executeReroute()
	case ActionReconnect:
		return e.executeReconnect()
	case ActionRestartDiscovery:
		return e.executeRestartDiscovery()
	case ActionAlertControlPlane:
		return e.executeAlertControlPlane()
	default:
		return fmt.Errorf("unknown healing action: %d", action)
	}
}

// executeReroute evicts peers that are unhealthy.
func (e *MeshHealingExecutor) executeReroute() error {
	if e.peerFn == nil || e.remover == nil {
		e.logger.Warn("reroute skipped: peerFn or remover not configured")
		return nil
	}

	peers := e.peerFn()
	evicted := 0
	for _, p := range peers {
		if !p.Healthy {
			e.remover.RemovePeer(p.NodeID)
			evicted++
			e.logger.Info("evicted unhealthy peer", "node_id", p.NodeID)
		}
	}

	e.logger.Info("reroute completed", "evicted", evicted, "total", len(peers))
	return nil
}

// executeReconnect evicts unhealthy peers and restarts discovery.
func (e *MeshHealingExecutor) executeReconnect() error {
	if e.peerFn != nil && e.remover != nil {
		peers := e.peerFn()
		for _, p := range peers {
			if !p.Healthy {
				e.remover.RemovePeer(p.NodeID)
			}
		}
	}

	if e.restarter != nil {
		if err := e.restarter.RestartDiscovery(); err != nil {
			return fmt.Errorf("restart discovery: %w", err)
		}
	}

	e.logger.Info("reconnect completed")
	return nil
}

// executeRestartDiscovery restarts discovery without evicting peers.
func (e *MeshHealingExecutor) executeRestartDiscovery() error {
	if e.restarter == nil {
		e.logger.Warn("restart discovery skipped: restarter not configured")
		return nil
	}

	if err := e.restarter.RestartDiscovery(); err != nil {
		return fmt.Errorf("restart discovery: %w", err)
	}

	e.logger.Info("discovery restarted")
	return nil
}

// executeAlertControlPlane sends a healing alert to the control plane.
func (e *MeshHealingExecutor) executeAlertControlPlane() error {
	if e.alerter == nil {
		e.logger.Warn("alert skipped: alerter not configured")
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := e.alerter.SendHealingAlert(ctx, e.nodeID, "auto-healing triggered", "alert_control_plane"); err != nil {
		return fmt.Errorf("send alert: %w", err)
	}

	e.logger.Info("control plane alerted")
	return nil
}
