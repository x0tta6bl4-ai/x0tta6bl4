// Package discovery implements mesh peer discovery.
// Wire-compatible with Python discovery/protocol.py:
//   - Multicast group 239.255.77.77:7777
//   - JSON messages over UDP
//   - MessageType enum 0x01-0x07
package discovery

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"sync"
	"time"
)

// Message types — must match Python MessageType enum exactly.
const (
	MsgAnnounce = 0x01
	MsgQuery    = 0x02
	MsgResponse = 0x03
	MsgPing     = 0x04
	MsgPong     = 0x05
	MsgJoin     = 0x06
	MsgLeave    = 0x07
)

const (
	DefaultMulticastGroup = "239.255.77.77"
	DefaultMulticastPort  = 7777
	AnnounceInterval      = 10 * time.Second
	PeerTimeout           = 60 * time.Second
	MaxMessageSize        = 4096
)

// PeerInfo matches Python PeerInfo.to_dict() format.
type PeerInfo struct {
	NodeID    string     `json:"node_id"`
	Addresses [][]any   `json:"addresses"` // [[ip, port], ...]
	Services  []string  `json:"services"`
	Version   string    `json:"version"`
	LastSeen  time.Time `json:"-"`
	RTTMS     float64   `json:"-"`
}

// Message matches Python DiscoveryMessage wire format.
type Message struct {
	Type    int             `json:"type"`
	Sender  string          `json:"sender"`
	Payload json.RawMessage `json:"payload"`
	TS      int64           `json:"ts"`
}

// AnnouncePayload is the payload for ANNOUNCE messages.
type AnnouncePayload struct {
	Peer PeerInfo `json:"peer"`
}

// ResponsePayload is the payload for RESPONSE messages.
type ResponsePayload struct {
	Peers []PeerInfo `json:"peers"`
}

// PingPayload contains the original timestamp.
type PingPayload struct {
	PingTS int64 `json:"ping_ts"`
}

// OnPeerFunc is a callback for peer events.
type OnPeerFunc func(peer PeerInfo)

// Discovery manages multicast peer discovery.
type Discovery struct {
	nodeID      string
	servicePort int
	services    []string
	mcastGroup  string
	mcastPort   int

	mu    sync.RWMutex
	peers map[string]*PeerInfo

	conn    *net.UDPConn
	running bool
	stopCh  chan struct{}

	OnPeerDiscovered OnPeerFunc
	OnPeerLost       OnPeerFunc

	logger *slog.Logger
}

// New creates a new Discovery instance.
func New(nodeID string, servicePort int, services []string, mcastGroup string, mcastPort int) *Discovery {
	if mcastGroup == "" {
		mcastGroup = DefaultMulticastGroup
	}
	if mcastPort == 0 {
		mcastPort = DefaultMulticastPort
	}
	if len(services) == 0 {
		services = []string{"mesh"}
	}

	return &Discovery{
		nodeID:      nodeID,
		servicePort: servicePort,
		services:    services,
		mcastGroup:  mcastGroup,
		mcastPort:   mcastPort,
		peers:       make(map[string]*PeerInfo),
		stopCh:      make(chan struct{}),
		logger:      slog.Default().With("component", "discovery"),
	}
}

// Start begins multicast listening and announcing.
func (d *Discovery) Start() error {
	addr, err := net.ResolveUDPAddr("udp4", fmt.Sprintf(":%d", d.mcastPort))
	if err != nil {
		return fmt.Errorf("resolve multicast addr: %w", err)
	}

	conn, err := net.ListenMulticastUDP("udp4", nil, &net.UDPAddr{
		IP:   net.ParseIP(d.mcastGroup),
		Port: d.mcastPort,
	})
	if err != nil {
		// Fallback: plain UDP if multicast fails (e.g., in containers)
		conn2, err2 := net.ListenUDP("udp4", addr)
		if err2 != nil {
			return fmt.Errorf("listen multicast: %w (fallback: %w)", err, err2)
		}
		conn = conn2
		d.logger.Warn("multicast unavailable, using plain UDP", "addr", addr)
	}

	d.conn = conn
	d.running = true

	go d.listenLoop()
	go d.announceLoop()
	go d.cleanupLoop()

	// Immediate announce
	d.sendAnnounce()

	d.logger.Info("discovery started",
		"group", d.mcastGroup,
		"port", d.mcastPort,
		"node_id", d.nodeID,
	)
	return nil
}

// Stop shuts down discovery gracefully.
func (d *Discovery) Stop() {
	if !d.running {
		return
	}
	d.running = false
	d.sendLeave()
	close(d.stopCh)
	if d.conn != nil {
		d.conn.Close()
	}
	d.logger.Info("discovery stopped")
}

// GetPeers returns all known live peers.
func (d *Discovery) GetPeers() []PeerInfo {
	d.mu.RLock()
	defer d.mu.RUnlock()

	peers := make([]PeerInfo, 0, len(d.peers))
	for _, p := range d.peers {
		peers = append(peers, *p)
	}
	return peers
}

// GetPeer returns a specific peer by node ID.
func (d *Discovery) GetPeer(nodeID string) *PeerInfo {
	d.mu.RLock()
	defer d.mu.RUnlock()
	if p, ok := d.peers[nodeID]; ok {
		cp := *p
		return &cp
	}
	return nil
}

// PeerCount returns number of known peers.
func (d *Discovery) PeerCount() int {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return len(d.peers)
}

// --- internal ---

func (d *Discovery) listenLoop() {
	buf := make([]byte, MaxMessageSize)
	for d.running {
		d.conn.SetReadDeadline(time.Now().Add(1 * time.Second))
		n, remoteAddr, err := d.conn.ReadFromUDP(buf)
		if err != nil {
			continue
		}
		d.handleMessage(buf[:n], remoteAddr)
	}
}

func (d *Discovery) announceLoop() {
	ticker := time.NewTicker(AnnounceInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			d.sendAnnounce()
		case <-d.stopCh:
			return
		}
	}
}

func (d *Discovery) cleanupLoop() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			d.cleanupExpired()
		case <-d.stopCh:
			return
		}
	}
}

func (d *Discovery) handleMessage(data []byte, addr *net.UDPAddr) {
	var msg Message
	if err := json.Unmarshal(data, &msg); err != nil {
		return
	}

	// Ignore our own messages
	if msg.Sender == d.nodeID {
		return
	}

	switch msg.Type {
	case MsgAnnounce:
		d.handleAnnounce(msg, addr)
	case MsgLeave:
		d.handleLeave(msg)
	case MsgQuery:
		d.handleQuery(msg, addr)
	case MsgPing:
		d.handlePing(msg, addr)
	}
}

func (d *Discovery) handleAnnounce(msg Message, addr *net.UDPAddr) {
	var payload AnnouncePayload
	if err := json.Unmarshal(msg.Payload, &payload); err != nil {
		return
	}

	peer := payload.Peer
	peer.LastSeen = time.Now()

	// Add sender address if not present
	senderAddr := []any{addr.IP.String(), d.servicePort}
	if len(peer.Addresses) > 0 {
		senderAddr = []any{addr.IP.String(), peer.Addresses[0][1]}
	}

	found := false
	for _, a := range peer.Addresses {
		if len(a) >= 2 && fmt.Sprint(a[0]) == addr.IP.String() {
			found = true
			break
		}
	}
	if !found {
		peer.Addresses = append(peer.Addresses, senderAddr)
	}

	d.mu.Lock()
	_, exists := d.peers[peer.NodeID]
	d.peers[peer.NodeID] = &peer
	d.mu.Unlock()

	if !exists {
		d.logger.Info("peer discovered", "node_id", peer.NodeID, "addr", addr)
		if d.OnPeerDiscovered != nil {
			d.OnPeerDiscovered(peer)
		}
	}
}

func (d *Discovery) handleLeave(msg Message) {
	d.mu.Lock()
	peer, exists := d.peers[msg.Sender]
	if exists {
		delete(d.peers, msg.Sender)
	}
	d.mu.Unlock()

	if exists {
		d.logger.Info("peer left", "node_id", msg.Sender)
		if d.OnPeerLost != nil && peer != nil {
			d.OnPeerLost(*peer)
		}
	}
}

func (d *Discovery) handleQuery(msg Message, addr *net.UDPAddr) {
	d.mu.RLock()
	peers := make([]PeerInfo, 0, len(d.peers))
	for _, p := range d.peers {
		peers = append(peers, *p)
	}
	d.mu.RUnlock()

	payload, _ := json.Marshal(ResponsePayload{Peers: peers})
	resp := Message{
		Type:    MsgResponse,
		Sender:  d.nodeID,
		Payload: payload,
		TS:      time.Now().UnixMilli(),
	}

	data, _ := json.Marshal(resp)
	d.conn.WriteToUDP(data, addr)
}

func (d *Discovery) handlePing(msg Message, addr *net.UDPAddr) {
	payload, _ := json.Marshal(PingPayload{PingTS: msg.TS})
	pong := Message{
		Type:    MsgPong,
		Sender:  d.nodeID,
		Payload: payload,
		TS:      time.Now().UnixMilli(),
	}

	data, _ := json.Marshal(pong)
	d.conn.WriteToUDP(data, addr)
}

func (d *Discovery) sendAnnounce() {
	localIP := getLocalIP()

	peer := PeerInfo{
		NodeID:    d.nodeID,
		Addresses: [][]any{{localIP, d.servicePort}},
		Services:  d.services,
		Version:   "1.0.0",
	}

	payload, _ := json.Marshal(AnnouncePayload{Peer: peer})
	msg := Message{
		Type:    MsgAnnounce,
		Sender:  d.nodeID,
		Payload: payload,
		TS:      time.Now().UnixMilli(),
	}

	data, _ := json.Marshal(msg)
	dst := &net.UDPAddr{IP: net.ParseIP(d.mcastGroup), Port: d.mcastPort}
	d.conn.WriteToUDP(data, dst)
}

func (d *Discovery) sendLeave() {
	payload, _ := json.Marshal(struct{}{})
	msg := Message{
		Type:    MsgLeave,
		Sender:  d.nodeID,
		Payload: payload,
		TS:      time.Now().UnixMilli(),
	}

	data, _ := json.Marshal(msg)
	dst := &net.UDPAddr{IP: net.ParseIP(d.mcastGroup), Port: d.mcastPort}
	d.conn.WriteToUDP(data, dst)
}

func (d *Discovery) cleanupExpired() {
	d.mu.Lock()
	defer d.mu.Unlock()

	now := time.Now()
	for nodeID, peer := range d.peers {
		if now.Sub(peer.LastSeen) > PeerTimeout {
			p := *peer
			delete(d.peers, nodeID)
			d.logger.Info("peer timeout", "node_id", nodeID)
			if d.OnPeerLost != nil {
				d.OnPeerLost(p)
			}
		}
	}
}

func getLocalIP() string {
	conn, err := net.Dial("udp", "8.8.8.8:80")
	if err != nil {
		return "127.0.0.1"
	}
	defer conn.Close()
	return conn.LocalAddr().(*net.UDPAddr).IP.String()
}
