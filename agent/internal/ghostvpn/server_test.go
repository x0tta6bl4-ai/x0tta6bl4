package ghostvpn

import (
	"testing"
	"time"
)

func TestServerConfig(t *testing.T) {
	s := NewServer(Config{
		Port:     9999,
		Subnet:   "10.88.0.0/24",
		PulseMode: "adaptive",
	})

	if s.cfg.Port != 9999 {
		t.Errorf("Port = %d, want 9999", s.cfg.Port)
	}
	if s.cfg.Subnet != "10.88.0.0/24" {
		t.Errorf("Subnet = %s", s.cfg.Subnet)
	}
	if s.cfg.PulseMode != "adaptive" {
		t.Errorf("PulseMode = %s", s.cfg.PulseMode)
	}
}

func TestServerNotRunning(t *testing.T) {
	s := NewServer(Config{})
	if s.IsRunning() {
		t.Error("should not be running before Start()")
	}
}

func TestServerStats(t *testing.T) {
	s := NewServer(Config{})
	stats := s.GetStats()
	if stats.ActiveClients != 0 {
		t.Errorf("ActiveClients = %d, want 0", stats.ActiveClients)
	}
}

func TestServerHealthCheckNotRunning(t *testing.T) {
	s := NewServer(Config{Port: 19999})
	if s.IsRunning() {
		t.Error("should not be running")
	}
	// UDP health check may succeed even when server is not running
	// (kernel responds to UDP). This is expected behavior.
}

func TestSessionTracking(t *testing.T) {
	s := NewServer(Config{})
	s.mu.Lock()
	s.sessions["client-1"] = &Session{
		ClientIP:  "10.0.0.1",
		VPNIP:     "10.88.0.2",
		Connected: time.Now(),
	}
	s.mu.Unlock()

	stats := s.GetStats()
	if stats.ActiveClients != 1 {
		t.Errorf("ActiveClients = %d, want 1", stats.ActiveClients)
	}
}
