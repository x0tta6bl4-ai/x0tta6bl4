// Package firstpartyvpn manages the FirstParty VPN subprocess.
// It starts, monitors, and controls the Python-based x0vpn_node.py.
package firstpartyvpn

import (
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"sync"
	"time"
)

// Config configures the FirstParty VPN node.
type Config struct {
	ScriptPath string
	ConfigPath string
	PythonPath string
	ProjectDir string
	Role string
}

// Session represents a connected VPN client (for server mode).
type Session struct {
	ClientIP   string    `json:"client_ip"`
	VPNIP      string    `json:"vpn_ip"`
	Connected  time.Time `json:"connected"`
	BytesSent  int64     `json:"bytes_sent"`
	BytesRecv  int64     `json:"bytes_recv"`
	Profile    string    `json:"profile"`
}

// Stats holds node statistics.
type Stats struct {
	ActiveClients int            `json:"active_clients"`
	TotalBytes    int64          `json:"total_bytes"`
	Uptime        time.Duration  `json:"uptime"`
	Sessions      []Session      `json:"sessions"`
}

// Node manages the FirstParty VPN subprocess.
type Node struct {
	cfg    Config
	logger *slog.Logger

	mu       sync.RWMutex
	cmd      *exec.Cmd
	running  bool
	started  time.Time
	sessions map[string]*Session
	restarts int

	stopCh chan struct{}
}

// NewNode creates a new FirstParty VPN node manager.
func NewNode(cfg Config) *Node {
	if cfg.PythonPath == "" {
		cfg.PythonPath = "python3"
	}
	if cfg.ProjectDir == "" {
		cfg.ProjectDir = "/mnt/projects"
	}
	if cfg.ScriptPath == "" {
		cfg.ScriptPath = cfg.ProjectDir + "/services/nl-server/firstparty-vpn-test/x0vpn_test_node.py"
	}
	if cfg.Role == "" {
		cfg.Role = "client-tun"
	}

	return &Node{
		cfg:      cfg,
		sessions: make(map[string]*Session),
		stopCh:   make(chan struct{}),
		logger:   slog.Default().With("component", "firstpartyvpn-node"),
	}
}

// Start starts the FirstParty VPN process.
func (n *Node) Start() error {
	n.mu.Lock()
	if n.running {
		n.mu.Unlock()
		return nil
	}
	n.running = true
	n.started = time.Now()
	n.mu.Unlock()

	args := []string{"-u", n.cfg.ScriptPath, n.cfg.Role}
	if n.cfg.ConfigPath != "" {
		args = append(args, "--config", n.cfg.ConfigPath)
	}
	args = append(args, "--allow-os-mutation")
	if n.cfg.Role == "server-tun" {
		args = append(args, "--uplink-interface", "eth0")
	}

	n.cmd = exec.Command("stdbuf", append([]string{"-oL", n.cfg.PythonPath}, args...)...)
	n.cmd.Dir = n.cfg.ProjectDir
	n.cmd.Env = append(os.Environ(), "PYTHONPATH="+n.cfg.ProjectDir)

	n.cmd.Stdout = os.Stdout
	n.cmd.Stderr = os.Stderr

	if err := n.cmd.Start(); err != nil {
		n.mu.Lock()
		n.running = false
		n.mu.Unlock()
		return fmt.Errorf("start firstpartyvpn: %w", err)
	}

	n.logger.Info("firstpartyvpn started", "pid", n.cmd.Process.Pid, "role", n.cfg.Role)

	go n.monitorLoop()

	return nil
}

// Stop stops the FirstParty VPN process.
func (n *Node) Stop() {
	n.mu.Lock()
	if !n.running {
		n.mu.Unlock()
		return
	}
	n.running = false
	n.mu.Unlock()

	close(n.stopCh)

	if n.cmd != nil && n.cmd.Process != nil {
		n.cmd.Process.Signal(os.Interrupt)
		n.cmd.Wait()
	}
	n.logger.Info("firstpartyvpn stopped")
}

// IsRunning returns whether the VPN server is running.
func (n *Node) IsRunning() bool {
	n.mu.RLock()
	defer n.mu.RUnlock()
	return n.running
}

// GetStats returns current server statistics.
func (n *Node) GetStats() Stats {
	n.mu.RLock()
	defer n.mu.RUnlock()

	sessions := make([]Session, 0, len(n.sessions))
	for _, sess := range n.sessions {
		sessions = append(sessions, *sess)
	}

	return Stats{
		ActiveClients: len(n.sessions),
		Uptime:        time.Since(n.started),
		Sessions:      sessions,
	}
}

func (n *Node) monitorLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	errCh := make(chan error, 1)
	go func() {
		errCh <- n.cmd.Wait()
	}()

	for {
		select {
		case <-n.stopCh:
			return
		case err := <-errCh:
			n.mu.Lock()
			n.running = false
			n.restarts++
			n.mu.Unlock()
			n.logger.Error("firstpartyvpn exited unexpectedly", "component", "firstpartyvpn-node", "error", err)
			return
		case <-ticker.C:
		}
	}
}
