// Package discovery implements mesh peer discovery.
// Supports both multicast UDP and mDNS/DNS-SD for automatic peer discovery.
package discovery

import (
	"context"
	"fmt"
	"log/slog"
	"net"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/grandcat/zeroconf"
)

const (
	// MdnsServiceType is the DNS-SD service type for x0tta6bl4 mesh nodes.
	MdnsServiceType = "_x0tta6bl4-mesh._tcp"
	// MdnsDomain is the default DNS-SD domain.
	MdnsDomain = "local."
	// MdnsBrowseInterval is how often to re-browse for peers.
	MdnsBrowseInterval = 30 * time.Second
	// MdnsPeerTimeout is how long before a peer is considered stale.
	MdnsPeerTimeout = 90 * time.Second
)

// MdnsPeerInfo represents a peer discovered via mDNS.
type MdnsPeerInfo struct {
	NodeID     string
	Addr       net.IP
	Port       int
	Version    string
	PQCEnabled bool
	Services   []string
	TXT        map[string]string
	LastSeen   time.Time
}

// MdnsConfig configures mDNS discovery.
type MdnsConfig struct {
	NodeID     string
	Port       int
	Version    string
	PQCEnabled bool
	Services   []string
	Domain     string
}

// MdnsDiscovery manages mDNS service registration and browsing.
type MdnsDiscovery struct {
	cfg    MdnsConfig
	logger *slog.Logger

	mu           sync.RWMutex
	peers        map[string]*MdnsPeerInfo
	server       *zeroconf.Server
	browseCtx    context.Context
	browseCancel context.CancelFunc
	running      bool

	OnPeerDiscovered func(peer MdnsPeerInfo)
	OnPeerLost       func(peer MdnsPeerInfo)
}

// NewMdnsDiscovery creates a new mDNS discovery instance.
func NewMdnsDiscovery(cfg MdnsConfig) *MdnsDiscovery {
	if cfg.Domain == "" {
		cfg.Domain = MdnsDomain
	}
	return &MdnsDiscovery{
		cfg:    cfg,
		peers:  make(map[string]*MdnsPeerInfo),
		logger: slog.Default().With("component", "mdns-discovery"),
	}
}

// Start begins mDNS registration and browsing.
func (d *MdnsDiscovery) Start() error {
	d.mu.Lock()
	if d.running {
		d.mu.Unlock()
		return nil
	}
	d.running = true
	d.mu.Unlock()

	txtRecords := []string{
		"node_id=" + d.cfg.NodeID,
		"version=" + d.cfg.Version,
		"pqc_enabled=" + strconv.FormatBool(d.cfg.PQCEnabled),
		"services=" + strings.Join(d.cfg.Services, ","),
	}

	// Use nodeID as instance name to avoid self-discovery
	instanceName := d.cfg.NodeID

	var err error
	d.server, err = zeroconf.Register(
		instanceName,
		MdnsServiceType,
		d.cfg.Domain,
		d.cfg.Port,
		txtRecords,
		nil,
	)
	if err != nil {
		d.mu.Lock()
		d.running = false
		d.mu.Unlock()
		return fmt.Errorf("mDNS register: %w", err)
	}

	d.logger.Info("mDNS service registered", "instance", instanceName, "port", d.cfg.Port)

	d.browseCtx, d.browseCancel = context.WithCancel(context.Background())
	go d.browseLoop()

	return nil
}

// Stop shuts down mDNS registration and browsing.
func (d *MdnsDiscovery) Stop() {
	d.mu.Lock()
	if !d.running {
		d.mu.Unlock()
		return
	}
	d.running = false
	d.mu.Unlock()

	if d.browseCancel != nil {
		d.browseCancel()
	}
	if d.server != nil {
		d.server.Shutdown()
	}
	d.logger.Info("mDNS discovery stopped")
}

// GetPeers returns all discovered peers.
func (d *MdnsDiscovery) GetPeers() []MdnsPeerInfo {
	d.mu.RLock()
	defer d.mu.RUnlock()

	peers := make([]MdnsPeerInfo, 0, len(d.peers))
	for _, p := range d.peers {
		peers = append(peers, *p)
	}
	return peers
}

// PeerCount returns the number of discovered peers.
func (d *MdnsDiscovery) PeerCount() int {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return len(d.peers)
}

func (d *MdnsDiscovery) browseLoop() {
	ticker := time.NewTicker(MdnsBrowseInterval)
	defer ticker.Stop()

	for {
		select {
		case <-d.browseCtx.Done():
			return
		case <-ticker.C:
			d.browse()
		}
	}
}

func (d *MdnsDiscovery) browse() {
	resolver, err := zeroconf.NewResolver(nil)
	if err != nil {
		d.logger.Warn("mDNS resolver creation failed", "error", err)
		return
	}

	entries := make(chan *zeroconf.ServiceEntry)
	ctx, cancel := context.WithTimeout(d.browseCtx, 10*time.Second)
	defer cancel()

	go func() {
		if err := resolver.Browse(ctx, MdnsServiceType, d.cfg.Domain, entries); err != nil {
			d.logger.Debug("mDNS browse error", "error", err)
		}
	}()

	for entry := range entries {
		d.processEntry(entry)
	}

	d.cleanupStale()
}

func (d *MdnsDiscovery) processEntry(entry *zeroconf.ServiceEntry) {
	if entry.Instance == d.cfg.NodeID || entry.Text == nil {
		return
	}

	txt := make(map[string]string)
	for _, t := range entry.Text {
		k, v := parseMDNSTxt(t)
		if k != "" {
			txt[k] = v
		}
	}

	nodeID := txt["node_id"]
	if nodeID == "" {
		nodeID = entry.Instance
	}

	var ip net.IP
	for _, addr := range entry.AddrIPv4 {
		ip = addr
		break
	}
	if ip == nil && len(entry.AddrIPv6) > 0 {
		ip = entry.AddrIPv6[0]
	}
	if ip == nil {
		return
	}

	peer := MdnsPeerInfo{
		NodeID:     nodeID,
		Addr:       ip,
		Port:       entry.Port,
		Version:    txt["version"],
		PQCEnabled: txt["pqc_enabled"] == "true",
		Services:   splitMDNSStrings(txt["services"], ","),
		TXT:        txt,
		LastSeen:   time.Now(),
	}

	d.mu.Lock()
	_, exists := d.peers[nodeID]
	d.peers[nodeID] = &peer
	d.mu.Unlock()

	if !exists {
		d.logger.Info("mDNS peer discovered", "node_id", nodeID, "addr", ip, "port", entry.Port)
		if d.OnPeerDiscovered != nil {
			d.OnPeerDiscovered(peer)
		}
	}
}

func (d *MdnsDiscovery) cleanupStale() {
	d.mu.Lock()
	defer d.mu.Unlock()

	now := time.Now()
	for nodeID, peer := range d.peers {
		if now.Sub(peer.LastSeen) > MdnsPeerTimeout {
			d.logger.Info("mDNS peer timed out", "node_id", nodeID)
			if d.OnPeerLost != nil {
				d.OnPeerLost(*peer)
			}
			delete(d.peers, nodeID)
		}
	}
}

func parseMDNSTxt(s string) (string, string) {
	for i := 0; i < len(s); i++ {
		if s[i] == '=' {
			return s[:i], s[i+1:]
		}
	}
	return s, ""
}

func joinStrings(ss []string, sep string) string {
	result := ""
	for i, s := range ss {
		if i > 0 {
			result += sep
		}
		result += s
	}
	return result
}

func splitMDNSStrings(s, sep string) []string {
	if s == "" {
		return nil
	}
	result := []string{}
	start := 0
	for i := 0; i <= len(s); i++ {
		if i == len(s) || s[i] == sep[0] {
			if i > start {
				result = append(result, s[start:i])
			}
			start = i + 1
		}
	}
	return result
}
