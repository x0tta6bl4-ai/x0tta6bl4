// Package mesh implements the core mesh node functionality.
// Handles peer connections, message routing, and multi-hop forwarding.
package mesh

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"sync"
	"time"

	"github.com/x0tta6bl4/agent/internal/mesh/discovery"
)

// Ensure Node implements the stats interface needed by telemetry and healing.
var _ interface{ GetStats() map[string]any } = (*Node)(nil)

// NodeState represents the current state of the mesh node.
type NodeState int

const (
	StateInit NodeState = iota
	StateConnecting
	StateActive
	StateDegraded
	StateStopped
)

func (s NodeState) String() string {
	switch s {
	case StateInit:
		return "init"
	case StateConnecting:
		return "connecting"
	case StateActive:
		return "active"
	case StateDegraded:
		return "degraded"
	case StateStopped:
		return "stopped"
	default:
		return "unknown"
	}
}

// Peer represents a connected peer in the mesh.
type Peer struct {
	NodeID    string
	Addr      *net.UDPAddr
	Latency   time.Duration
	LastSeen  time.Time
	BytesSent int64
	BytesRecv int64
	Healthy   bool
}

// MessageHandler is a callback for received mesh messages.
type MessageHandler func(data []byte, sender string, addr *net.UDPAddr)

// Node is the core mesh node.
type Node struct {
	ID         string
	ListenPort int
	State      NodeState

	mu    sync.RWMutex
	peers map[string]*Peer
	conn  *net.UDPConn

	discovery  *discovery.Discovery
	handlers   []MessageHandler

	stopCh  chan struct{}
	logger  *slog.Logger

	// Stats
	msgSent int64
	msgRecv int64
	started time.Time
}

// NewNode creates a new mesh node.
func NewNode(nodeID string, listenPort int, disc *discovery.Discovery) *Node {
	return &Node{
		ID:         nodeID,
		ListenPort: listenPort,
		State:      StateInit,
		peers:      make(map[string]*Peer),
		discovery:  disc,
		stopCh:     make(chan struct{}),
		logger:     slog.Default().With("component", "mesh-node", "node_id", nodeID),
	}
}

// Start initializes the node and begins listening.
func (n *Node) Start() error {
	addr, err := net.ResolveUDPAddr("udp4", fmt.Sprintf(":%d", n.ListenPort))
	if err != nil {
		return fmt.Errorf("resolve addr: %w", err)
	}

	conn, err := net.ListenUDP("udp4", addr)
	if err != nil {
		return fmt.Errorf("listen UDP: %w", err)
	}

	n.conn = conn
	n.State = StateConnecting
	n.started = time.Now()

	// Wire discovery callbacks
	if n.discovery != nil {
		n.discovery.OnPeerDiscovered = func(peer discovery.PeerInfo) {
			n.addPeerFromDiscovery(peer)
		}
		n.discovery.OnPeerLost = func(peer discovery.PeerInfo) {
			n.removePeer(peer.NodeID)
		}
		if err := n.discovery.Start(); err != nil {
			n.logger.Warn("discovery failed to start", "error", err)
		}
	}

	go n.listenLoop()
	go n.healthCheckLoop()

	n.State = StateActive
	n.logger.Info("mesh node started", "port", n.ListenPort)
	return nil
}

// Stop gracefully shuts down the node.
func (n *Node) Stop() {
	n.State = StateStopped
	close(n.stopCh)

	if n.discovery != nil {
		n.discovery.Stop()
	}

	if n.conn != nil {
		n.conn.Close()
	}

	n.logger.Info("mesh node stopped")
}

// OnMessage registers a message handler.
func (n *Node) OnMessage(handler MessageHandler) {
	n.handlers = append(n.handlers, handler)
}

// SendTo sends data to a specific peer.
func (n *Node) SendTo(peerID string, data []byte) error {
	n.mu.RLock()
	peer, ok := n.peers[peerID]
	n.mu.RUnlock()

	if !ok {
		return fmt.Errorf("peer not found: %s", peerID)
	}

	_, err := n.conn.WriteToUDP(data, peer.Addr)
	if err != nil {
		return fmt.Errorf("send to %s: %w", peerID, err)
	}

	n.mu.Lock()
	peer.BytesSent += int64(len(data))
	n.msgSent++
	n.mu.Unlock()

	return nil
}

// Broadcast sends data to all peers.
func (n *Node) Broadcast(data []byte) {
	n.mu.RLock()
	peers := make([]*Peer, 0, len(n.peers))
	for _, p := range n.peers {
		peers = append(peers, p)
	}
	n.mu.RUnlock()

	for _, peer := range peers {
		n.conn.WriteToUDP(data, peer.Addr)
		n.mu.Lock()
		peer.BytesSent += int64(len(data))
		n.msgSent++
		n.mu.Unlock()
	}
}

// GetPeers returns the current peer list.
func (n *Node) GetPeers() []Peer {
	n.mu.RLock()
	defer n.mu.RUnlock()

	peers := make([]Peer, 0, len(n.peers))
	for _, p := range n.peers {
		peers = append(peers, *p)
	}
	return peers
}

// GetStats returns node statistics.
func (n *Node) GetStats() map[string]any {
	n.mu.RLock()
	defer n.mu.RUnlock()

	healthyCount := 0
	for _, p := range n.peers {
		if p.Healthy {
			healthyCount++
		}
	}

	healthScore := 0.0
	if len(n.peers) > 0 {
		healthScore = float64(healthyCount) / float64(len(n.peers))
	}

	return map[string]any{
		"node_id":       n.ID,
		"state":         n.State.String(),
		"peers_total":   len(n.peers),
		"peers_healthy": healthyCount,
		"health_score":  healthScore,
		"messages_sent": n.msgSent,
		"messages_recv": n.msgRecv,
		"uptime_sec":    time.Since(n.started).Seconds(),
	}
}

// --- internal ---

func (n *Node) listenLoop() {
	buf := make([]byte, 65535)
	for {
		select {
		case <-n.stopCh:
			return
		default:
		}

		n.conn.SetReadDeadline(time.Now().Add(1 * time.Second))
		nBytes, remoteAddr, err := n.conn.ReadFromUDP(buf)
		if err != nil {
			continue
		}

		data := make([]byte, nBytes)
		copy(data, buf[:nBytes])

		n.mu.Lock()
		n.msgRecv++
		n.mu.Unlock()

		// Try to identify sender
		senderID := ""
		n.mu.RLock()
		for id, p := range n.peers {
			if p.Addr.IP.Equal(remoteAddr.IP) && p.Addr.Port == remoteAddr.Port {
				senderID = id
				break
			}
		}
		n.mu.RUnlock()

		// Update peer stats
		if senderID != "" {
			n.mu.Lock()
			if p, ok := n.peers[senderID]; ok {
				p.LastSeen = time.Now()
				p.BytesRecv += int64(nBytes)
			}
			n.mu.Unlock()
		}

		// Dispatch to handlers
		for _, handler := range n.handlers {
			handler(data, senderID, remoteAddr)
		}
	}
}

func (n *Node) healthCheckLoop() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			n.checkPeerHealth()
		case <-n.stopCh:
			return
		}
	}
}

func (n *Node) checkPeerHealth() {
	n.mu.Lock()
	defer n.mu.Unlock()

	now := time.Now()
	degraded := false
	for _, peer := range n.peers {
		if now.Sub(peer.LastSeen) > 30*time.Second {
			peer.Healthy = false
			degraded = true
		} else {
			peer.Healthy = true
		}
	}

	if degraded && n.State == StateActive {
		n.State = StateDegraded
	} else if !degraded && n.State == StateDegraded {
		n.State = StateActive
	}
}

func (n *Node) addPeerFromDiscovery(info discovery.PeerInfo) {
	if len(info.Addresses) == 0 {
		return
	}

	// Parse first address
	addrParts := info.Addresses[0]
	if len(addrParts) < 2 {
		return
	}

	ip := fmt.Sprint(addrParts[0])
	port := 0
	switch v := addrParts[1].(type) {
	case float64:
		port = int(v)
	case json.Number:
		p, _ := v.Int64()
		port = int(p)
	case int:
		port = v
	default:
		fmt.Sscanf(fmt.Sprint(v), "%d", &port)
	}

	if port == 0 {
		return
	}

	udpAddr := &net.UDPAddr{IP: net.ParseIP(ip), Port: port}

	n.mu.Lock()
	n.peers[info.NodeID] = &Peer{
		NodeID:   info.NodeID,
		Addr:     udpAddr,
		LastSeen: time.Now(),
		Healthy:  true,
	}
	n.mu.Unlock()

	n.logger.Info("peer added", "node_id", info.NodeID, "addr", udpAddr)
}

func (n *Node) removePeer(nodeID string) {
	n.mu.Lock()
	delete(n.peers, nodeID)
	n.mu.Unlock()

	n.logger.Info("peer removed", "node_id", nodeID)
}
