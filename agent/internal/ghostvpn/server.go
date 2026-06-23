// Package ghostvpn manages the GhostVPN server subprocess.
// It starts, monitors, and controls the Python-based GhostVPN server.
package ghostvpn

import (
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/exec"
	"sync"
	"time"
)

// Config configures the GhostVPN server.
type Config struct {
	// ServerScript is the path to ghost_vpn_server.py.
	ServerScript string
	// PythonPath is the path to python3.
	PythonPath string
	// Port is the VPN listen port (UDP).
	Port int
	// Subnet is the VPN client subnet.
	Subnet string
	// AuthKey is the authentication key.
	AuthKey string
	// PulseMode is the traffic obfuscation mode.
	PulseMode string
	// ProjectDir is the project root directory.
	ProjectDir string
}

// Session represents a connected VPN client.
type Session struct {
	ClientIP   string    `json:"client_ip"`
	VPNIP      string    `json:"vpn_ip"`
	Connected  time.Time `json:"connected"`
	BytesSent  int64     `json:"bytes_sent"`
	BytesRecv  int64     `json:"bytes_recv"`
	Profile    string    `json:"profile"`
}

// Stats holds server statistics.
type Stats struct {
	ActiveClients int            `json:"active_clients"`
	TotalBytes    int64          `json:"total_bytes"`
	Uptime        time.Duration  `json:"uptime"`
	Sessions      []Session      `json:"sessions"`
}

// Server manages the GhostVPN server subprocess.
type Server struct {
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

// NewServer creates a new GhostVPN server manager.
func NewServer(cfg Config) *Server {
	if cfg.PythonPath == "" {
		cfg.PythonPath = "python3"
	}
	if cfg.Port == 0 {
		cfg.Port = 9999
	}
	if cfg.Subnet == "" {
		cfg.Subnet = "10.88.0.0/24"
	}
	if cfg.PulseMode == "" {
		cfg.PulseMode = "adaptive"
	}
	if cfg.ProjectDir == "" {
		cfg.ProjectDir = "/opt/x0tta6bl4"
	}
	if cfg.ServerScript == "" {
		cfg.ServerScript = cfg.ProjectDir + "/services/nl-server/ghost-vpn/ghost_vpn_server.py"
	}

	return &Server{
		cfg:      cfg,
		sessions: make(map[string]*Session),
		stopCh:   make(chan struct{}),
		logger:   slog.Default().With("component", "ghostvpn-server"),
	}
}

// Start starts the GhostVPN server process.
func (s *Server) Start() error {
	s.mu.Lock()
	if s.running {
		s.mu.Unlock()
		return nil
	}
	s.running = true
	s.started = time.Now()
	s.mu.Unlock()

	// Build command
	args := []string{s.cfg.ServerScript}
	s.cmd = exec.Command(s.cfg.PythonPath, args...)
	s.cmd.Dir = s.cfg.ProjectDir
	s.cmd.Env = append(os.Environ(),
		fmt.Sprintf("VPN_PORT=%d", s.cfg.Port),
		fmt.Sprintf("VPN_SUBNET=%s", s.cfg.Subnet),
		fmt.Sprintf("PULSE_MODE=%s", s.cfg.PulseMode),
	)
	if s.cfg.AuthKey != "" {
		s.cmd.Env = append(s.cmd.Env, fmt.Sprintf("VPN_AUTH_KEY=%s", s.cfg.AuthKey))
	}

	s.cmd.Stdout = os.Stdout
	s.cmd.Stderr = os.Stderr

	if err := s.cmd.Start(); err != nil {
		s.mu.Lock()
		s.running = false
		s.mu.Unlock()
		return fmt.Errorf("start ghost-vpn: %w", err)
	}

	s.logger.Info("ghost-vpn started", "pid", s.cmd.Process.Pid, "port", s.cfg.Port)

	// Start monitoring
	go s.monitorLoop()

	return nil
}

// Stop stops the GhostVPN server process.
func (s *Server) Stop() {
	s.mu.Lock()
	if !s.running {
		s.mu.Unlock()
		return
	}
	s.running = false
	s.mu.Unlock()

	close(s.stopCh)

	if s.cmd != nil && s.cmd.Process != nil {
		s.cmd.Process.Signal(os.Interrupt)
		s.cmd.Wait()
	}
	s.logger.Info("ghost-vpn stopped")
}

// IsRunning returns whether the VPN server is running.
func (s *Server) IsRunning() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.running
}

// GetStats returns current server statistics.
func (s *Server) GetStats() Stats {
	s.mu.RLock()
	defer s.mu.RUnlock()

	sessions := make([]Session, 0, len(s.sessions))
	for _, sess := range s.sessions {
		sessions = append(sessions, *sess)
	}

	return Stats{
		ActiveClients: len(s.sessions),
		Uptime:        time.Since(s.started),
		Sessions:      sessions,
	}
}

// HealthCheck verifies the VPN server is responsive.
func (s *Server) HealthCheck() error {
	conn, err := net.DialTimeout("udp4",
		fmt.Sprintf("127.0.0.1:%d", s.cfg.Port),
		2*time.Second,
	)
	if err != nil {
		return fmt.Errorf("VPN health check failed: %w", err)
	}
	conn.Close()
	return nil
}

func (s *Server) monitorLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-s.stopCh:
			return
		case <-ticker.C:
			s.checkAndRestart()
		}
	}
}

func (s *Server) checkAndRestart() {
	s.mu.RLock()
	running := s.running
	cmd := s.cmd
	s.mu.RUnlock()

	if !running {
		return
	}

	// Check if process is still alive
	if cmd != nil && cmd.Process != nil {
		// Try to find process - if it doesn't exist, ErrProcessDone
		err := cmd.Process.Release()
		if err == nil {
			// Process was alive, we just released it (need to re-track)
			// This is a simplified check - in production would use pidfile
			s.mu.Lock()
			s.running = false
			s.mu.Unlock()
		}
		// For now, rely on health check
	}

	if err := s.HealthCheck(); err != nil {
		s.logger.Warn("VPN health check failed, restarting", "error", err, "restarts", s.restarts)
		s.restarts++
		s.mu.Lock()
		s.running = false
		s.mu.Unlock()
		if err := s.Start(); err != nil {
			s.logger.Error("VPN restart failed", "error", err)
		}
	}
}

// GetRestarts returns the number of restarts.
func (s *Server) GetRestarts() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.restarts
}
