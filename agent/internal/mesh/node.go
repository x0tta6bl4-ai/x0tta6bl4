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

	"github.com/x0tta6bl4/agent/internal/crypto/pqc"
	"github.com/x0tta6bl4/agent/internal/mesh/discovery"
)

// Ensure Node implements the stats interface needed by telemetry and healing.
var _ interface{ GetStats() map[string]any } = (*Node)(nil)

// Message prefix bytes for protocol negotiation.
const (
	PrefixRaw    byte = 0x00 // plaintext message
	PrefixPQC    byte = 0x01 // PQC1 encrypted message
	PrefixPQCInit byte = 0x10 // PQC handshake init
	PrefixPQCResp byte = 0x11 // PQC handshake response
)

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
	tunnelMgr  *pqc.TunnelManager

	// Track which peers we've initiated PQC handshakes to.
	// Only process responses from these peers.
	pendingHandshakes map[string]bool

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
		ID:                nodeID,
		ListenPort:        listenPort,
		State:             StateInit,
		peers:             make(map[string]*Peer),
		discovery:         disc,
		pendingHandshakes: make(map[string]bool),
		stopCh:            make(chan struct{}),
		logger:            slog.Default().With("component", "mesh-node", "node_id", nodeID),
	}
}

// SetTunnelManager enables PQC encryption on the mesh data path.
// Must be called before Start(). If nil, the node operates in plaintext mode.
func (n *Node) SetTunnelManager(tm *pqc.TunnelManager) {
	n.tunnelMgr = tm
	n.logger.Info("PQC tunnel manager attached")
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
// If PQC is enabled and a session exists, data is encrypted automatically.
func (n *Node) SendTo(peerID string, data []byte) error {
	n.mu.RLock()
	peer, ok := n.peers[peerID]
	n.mu.RUnlock()

	if !ok {
		return fmt.Errorf("peer not found: %s", peerID)
	}

	// PQC encrypt if tunnel is available and session exists
	outData := data
	if n.tunnelMgr != nil && n.tunnelMgr.HasSession(peerID) {
		wrapped, err := n.tunnelMgr.WrapPacket(data, peerID)
		if err != nil {
			return fmt.Errorf("pqc wrap: %w", err)
		}
		outData = append([]byte{PrefixPQC}, wrapped...)
	} else if n.tunnelMgr != nil {
		outData = append([]byte{PrefixRaw}, data...)
	}

	_, err := n.conn.WriteToUDP(outData, peer.Addr)
	if err != nil {
		return fmt.Errorf("send to %s: %w", peerID, err)
	}

	n.mu.Lock()
	peer.BytesSent += int64(len(outData))
	n.msgSent++
	n.mu.Unlock()

	return nil
}

// Broadcast sends data to all peers.
// If PQC is enabled, each peer's data is encrypted with their respective session key.
func (n *Node) Broadcast(data []byte) {
	n.mu.RLock()
	peers := make([]*Peer, 0, len(n.peers))
	for _, p := range n.peers {
		peers = append(peers, p)
	}
	n.mu.RUnlock()

	for _, peer := range peers {
		outData := data
		if n.tunnelMgr != nil && n.tunnelMgr.HasSession(peer.NodeID) {
			wrapped, err := n.tunnelMgr.WrapPacket(data, peer.NodeID)
			if err != nil {
				n.logger.Warn("pqc wrap failed for broadcast", "peer", peer.NodeID, "error", err)
				outData = append([]byte{PrefixRaw}, data...)
			} else {
				outData = append([]byte{PrefixPQC}, wrapped...)
			}
		} else if n.tunnelMgr != nil {
			outData = append([]byte{PrefixRaw}, data...)
		}

		n.conn.WriteToUDP(outData, peer.Addr)
		n.mu.Lock()
		peer.BytesSent += int64(len(outData))
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

		rawData := make([]byte, nBytes)
		copy(rawData, buf[:nBytes])

		n.mu.Lock()
		n.msgRecv++
		n.mu.Unlock()

		// Identify sender
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

		// Protocol dispatch
		data := rawData
		if len(rawData) == 0 {
			continue
		}

		switch rawData[0] {
		case PrefixPQC:
			// PQC encrypted data — decrypt
			if n.tunnelMgr != nil && senderID != "" {
				decrypted, err := n.tunnelMgr.UnwrapPacket(rawData[1:], senderID)
				if err == nil {
					data = decrypted
					n.logger.Debug("PQC decrypted", "peer", senderID, "bytes", len(decrypted))
				} else {
					n.logger.Warn("PQC decrypt failed", "peer", senderID, "error", err)
					continue // drop corrupted packets
				}
			} else {
				continue // no PQC session, drop
			}

		case PrefixPQCInit:
			// PQC handshake init — process and send response
			if n.tunnelMgr != nil {
				n.tryProcessPQCInit(rawData[1:], remoteAddr)
			}
			continue // consumed

		case PrefixPQCResp:
			// PQC handshake response — process if we initiated
			if n.tunnelMgr != nil && senderID != "" {
				n.tryProcessPQCResponse(rawData[1:], senderID)
			}
			continue // consumed

		case PrefixRaw:
			data = rawData[1:]

		default:
			// Unknown prefix — treat as raw (backward compat with old nodes)
			data = rawData
		}

		// Dispatch to handlers
		for _, handler := range n.handlers {
			handler(data, senderID, remoteAddr)
		}
	}
}

// tryProcessPQCInit processes an incoming PQC handshake init message.
func (n *Node) tryProcessPQCInit(data []byte, senderAddr *net.UDPAddr) {
	peerID, _, respMsg, err := n.tunnelMgr.ProcessHandshakeInit(data)
	if err != nil {
		n.logger.Warn("PQC handshake init failed", "error", err)
		return
	}
	wireMsg := append([]byte{PrefixPQCResp}, respMsg...)
	n.conn.WriteToUDP(wireMsg, senderAddr)
	n.logger.Info("PQC handshake completed (responder)", "peer", peerID)
}

// tryProcessPQCResponse processes an incoming PQC handshake response message.
func (n *Node) tryProcessPQCResponse(data []byte, senderID string) {
	n.mu.RLock()
	isPending := n.pendingHandshakes[senderID]
	n.mu.RUnlock()

	if !isPending {
		return
	}

	peerID, _, err := n.tunnelMgr.ProcessHandshakeResponse(data)
	if err != nil {
		n.logger.Warn("PQC handshake response failed", "peer", senderID, "error", err)
		n.mu.Lock()
		delete(n.pendingHandshakes, senderID)
		n.mu.Unlock()
		return
	}

	n.mu.Lock()
	delete(n.pendingHandshakes, senderID)
	n.mu.Unlock()
	n.logger.Info("PQC handshake completed (initiator)", "peer", peerID)
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

	// Initiate PQC handshake if tunnel manager is available
	if n.tunnelMgr != nil {
		go n.initiatePQCHandshake(info.NodeID)
	}
}

// shouldInitiatePQCHandshake returns true if this node should be the PQC handshake initiator.
// Uses lexicographic tiebreaker on nodeIDs to avoid simultaneous init race.
func (n *Node) shouldInitiatePQCHandshake(peerID string) bool {
	return n.ID < peerID
}

// initiatePQCHandshake sends a PQC handshake init to a peer and processes the response.
func (n *Node) initiatePQCHandshake(peerID string) {
	n.mu.RLock()
	peer, ok := n.peers[peerID]
	n.mu.RUnlock()
	if !ok {
		return
	}

	// Only initiate if we "win" the tiebreaker
	if !n.shouldInitiatePQCHandshake(peerID) {
		n.logger.Debug("PQC handshake: waiting for peer to initiate", "peer", peerID)
		return
	}

	// Create and send handshake init
	initMsg, err := n.tunnelMgr.CreateHandshakeInit()
	if err != nil {
		n.logger.Warn("PQC handshake init failed", "peer", peerID, "error", err)
		return
	}

	// Mark as pending before sending
	n.mu.Lock()
	n.pendingHandshakes[peerID] = true
	n.mu.Unlock()

	// Send init with type prefix
	wireMsg := append([]byte{PrefixPQCInit}, initMsg...)
	_, err = n.conn.WriteToUDP(wireMsg, peer.Addr)
	if err != nil {
		n.mu.Lock()
		delete(n.pendingHandshakes, peerID)
		n.mu.Unlock()
		n.logger.Warn("PQC handshake init send failed", "peer", peerID, "error", err)
		return
	}

	n.logger.Info("PQC handshake initiated", "peer", peerID, "tiebreaker", n.ID+" < "+peerID)
}

// HandlePQCMessage processes an incoming PQC handshake message.
// Call this from a message handler registered via OnMessage.
// Returns true if the message was a PQC handshake message.
func (n *Node) HandlePQCMessage(data []byte, senderID string, senderAddr *net.UDPAddr) bool {
	if n.tunnelMgr == nil || len(data) < 2 {
		return false
	}

	// Check if this looks like a PQC handshake response (has our nodeID prefix)
	// The response format: [node_id_len:2][node_id][ciphertext][sign_pubkey][signature]
	nodeIDLen := int(data[0])<<8 | int(data[1])
	if nodeIDLen != len(n.ID) {
		return false
	}
	if len(data) < 2+nodeIDLen {
		return false
	}
	candidateID := string(data[2 : 2+nodeIDLen])
	if candidateID != n.ID {
		return false
	}

	// This is a PQC handshake response addressed to us
	peerID, _, respMsg, err := n.tunnelMgr.ProcessHandshakeInit(data)
	if err != nil {
		n.logger.Warn("PQC handshake init process failed", "error", err)
		return true
	}

	// Send response back
	wireMsg := append([]byte{PrefixRaw}, respMsg...)
	_, err = n.conn.WriteToUDP(wireMsg, senderAddr)
	if err != nil {
		n.logger.Warn("PQC handshake response send failed", "error", err)
		return true
	}

	n.logger.Info("PQC handshake completed (responder)", "peer", peerID)
	return true
}

// InjectPeer directly adds a peer to the node (for testing or manual configuration).
func (n *Node) InjectPeer(peerID, ip string, port int) {
	addr := &net.UDPAddr{IP: net.ParseIP(ip), Port: port}
	n.mu.Lock()
	n.peers[peerID] = &Peer{
		NodeID:   peerID,
		Addr:     addr,
		LastSeen: time.Now(),
		Healthy:  true,
	}
	n.mu.Unlock()
	n.logger.Info("peer injected", "node_id", peerID, "addr", addr)

	// Initiate PQC handshake if tunnel manager is available
	if n.tunnelMgr != nil {
		go n.initiatePQCHandshake(peerID)
	}
}

func (n *Node) removePeer(nodeID string) {
	n.mu.Lock()
	delete(n.peers, nodeID)
	n.mu.Unlock()

	n.logger.Info("peer removed", "node_id", nodeID)
}

// RemovePeer drops a peer from the node's peer table and from discovery.
// Exposed for the healing executor to evict unhealthy peers.
func (n *Node) RemovePeer(nodeID string) {
	n.removePeer(nodeID)
	if n.discovery != nil {
		n.discovery.RemovePeer(nodeID)
	}
}

// RestartDiscovery stops and restarts the discovery subsystem.
// Exposed for the healing executor to force re-announcements.
func (n *Node) RestartDiscovery() error {
	if n.discovery == nil {
		return nil
	}
	return n.discovery.Restart()
}
