// Package yggdrasil manages the Yggdrasil mesh network subprocess.
// It starts, monitors, and controls Yggdrasil for IPv6 mesh routing.
package yggdrasil

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"
)

// Config configures the Yggdrasil client.
type Config struct {
	// ConfigPath is the path to yggdrasil.conf.
	ConfigPath string
	// BinaryPath is the path to the yggdrasil binary.
	BinaryPath string
	// Peers is the list of peer addresses (tcp://host:port).
	Peers []string
	// Listen is the listen address for incoming connections.
	Listen string
	// IfName is the network interface name.
	IfName string
}

// Peer represents a Yggdrasil mesh peer.
type Peer struct {
	Address  string `json:"address"`
	Port     int    `json:"port"`
	IPv6     string `json:"ipv6"`
	Online   bool   `json:"online"`
	Latency  int    `json:"latency"`
}

// SelfInfo represents the local node's Yggdrasil info.
type SelfInfo struct {
	IPv6    string `json:"ipv6"`
	Key     string `json:"key"`
	Subnet  string `json:"subnet"`
	Version string `json:"version"`
}

// Client manages the Yggdrasil subprocess.
type Client struct {
	cfg    Config
	logger *slog.Logger

	mu       sync.RWMutex
	cmd      *exec.Cmd
	running  bool
	selfInfo *SelfInfo
	peers    map[string]*Peer

	stopCh chan struct{}
}

// NewClient creates a new Yggdrasil client.
func NewClient(cfg Config) *Client {
	if cfg.ConfigPath == "" {
		cfg.ConfigPath = "/etc/yggdrasil/yggdrasil.conf"
	}
	if cfg.BinaryPath == "" {
		cfg.BinaryPath = "yggdrasil"
	}
	if cfg.Listen == "" {
		cfg.Listen = "tcp://0.0.0.0:9001"
	}
	return &Client{
		cfg:    cfg,
		peers:  make(map[string]*Peer),
		stopCh: make(chan struct{}),
		logger: slog.Default().With("component", "yggdrasil-client"),
	}
}

// Start starts the Yggdrasil process.
func (c *Client) Start() error {
	c.mu.Lock()
	if c.running {
		c.mu.Unlock()
		return nil
	}
	c.running = true
	c.mu.Unlock()

	// Ensure config exists
	if err := c.ensureConfig(); err != nil {
		return fmt.Errorf("ensure config: %w", err)
	}

	// Start yggdrasil process
	c.cmd = exec.Command(c.cfg.BinaryPath, "--config", c.cfg.ConfigPath)
	c.cmd.Stdout = os.Stdout
	c.cmd.Stderr = os.Stderr

	if err := c.cmd.Start(); err != nil {
		c.mu.Lock()
		c.running = false
		c.mu.Unlock()
		return fmt.Errorf("start yggdrasil: %w", err)
	}

	c.logger.Info("yggdrasil started", "pid", c.cmd.Process.Pid, "config", c.cfg.ConfigPath)

	// Start monitoring
	go c.monitorLoop()

	return nil
}

// Stop stops the Yggdrasil process.
func (c *Client) Stop() {
	c.mu.Lock()
	if !c.running {
		c.mu.Unlock()
		return
	}
	c.running = false
	c.mu.Unlock()

	close(c.stopCh)

	if c.cmd != nil && c.cmd.Process != nil {
		c.cmd.Process.Signal(os.Interrupt)
		c.cmd.Wait()
	}
	c.logger.Info("yggdrasil stopped")
}

// IsRunning returns whether Yggdrasil is running.
func (c *Client) IsRunning() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.running
}

// GetSelf returns the local node's Yggdrasil info.
func (c *Client) GetSelf() (*SelfInfo, error) {
	output, err := c.yggdrasilctl("getself")
	if err != nil {
		return nil, err
	}
	return parseSelfInfo(output), nil
}

// GetPeers returns the list of connected peers.
func (c *Client) GetPeers() []Peer {
	c.mu.RLock()
	defer c.mu.RUnlock()

	peers := make([]Peer, 0, len(c.peers))
	for _, p := range c.peers {
		peers = append(peers, *p)
	}
	return peers
}

// GetIPv6 returns the local IPv6 address.
func (c *Client) GetIPv6() string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.selfInfo != nil {
		return c.selfInfo.IPv6
	}
	return ""
}

func (c *Client) monitorLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-c.stopCh:
			return
		case <-ticker.C:
			c.refresh()
		}
	}
}

func (c *Client) refresh() {
	// Get self info
	self, err := c.GetSelf()
	if err != nil {
		c.logger.Warn("failed to get yggdrasil self info", "error", err)
		return
	}

	c.mu.Lock()
	c.selfInfo = self
	c.mu.Unlock()

	// Get peers
	peers, err := c.getPeersFromYggdrasil()
	if err != nil {
		c.logger.Warn("failed to get yggdrasil peers", "error", err)
		return
	}

	c.mu.Lock()
	c.peers = peers
	c.mu.Unlock()
}

func (c *Client) getPeersFromYggdrasil() (map[string]*Peer, error) {
	output, err := c.yggdrasilctl("getpeers")
	if err != nil {
		return nil, err
	}
	return parsePeers(output), nil
}

func (c *Client) yggdrasilctl(args ...string) (string, error) {
	cmdArgs := append([]string{"yggdrasilctl"}, args...)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, cmdArgs[0], cmdArgs[1:]...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("yggdrasilctl %s: %w (output: %s)", strings.Join(args, " "), err, string(output))
	}
	return string(output), nil
}

func (c *Client) ensureConfig() error {
	if _, err := os.Stat(c.cfg.ConfigPath); err == nil {
		return nil // config exists
	}

	// Generate default config
	config := map[string]interface{}{
		"Listen": []string{c.cfg.Listen},
		"Peers":  c.cfg.Peers,
		"IfName": c.cfg.IfName,
	}

	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}

	if err := os.MkdirAll(strings.TrimSuffix(c.cfg.ConfigPath, "/yggdrasil.conf"), 0o755); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}

	if err := os.WriteFile(c.cfg.ConfigPath, data, 0o644); err != nil {
		return fmt.Errorf("write config: %w", err)
	}

	c.logger.Info("yggdrasil config created", "path", c.cfg.ConfigPath)
	return nil
}

func parseSelfInfo(output string) *SelfInfo {
	info := &SelfInfo{}
	for _, line := range strings.Split(output, "\n") {
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])
		switch {
		case strings.Contains(key, "IPv6"):
			info.IPv6 = value
		case strings.Contains(key, "Key"):
			info.Key = value
		case strings.Contains(key, "Subnet"):
			info.Subnet = value
		case strings.Contains(key, "Version"):
			info.Version = value
		}
	}
	return info
}

func parsePeers(output string) map[string]*Peer {
	peers := make(map[string]*Peer)
	for _, line := range strings.Split(output, "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		// Simple parsing - in production would use JSON output
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			peer := &Peer{
				Address: parts[0],
				Online:  true,
			}
			peers[parts[0]] = peer
		}
	}
	return peers
}
