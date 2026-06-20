package discovery

import (
	"testing"
	"time"
)

func TestMdnsDiscoveryConfig(t *testing.T) {
	cfg := MdnsConfig{
		NodeID:     "test-node",
		Port:       5000,
		Version:    "1.0.0",
		PQCEnabled: true,
		Services:   []string{"mesh", "pqc"},
		Domain:     "local.",
	}

	d := NewMdnsDiscovery(cfg)

	if d.cfg.NodeID != "test-node" {
		t.Errorf("NodeID = %s, want test-node", d.cfg.NodeID)
	}
	if d.cfg.Port != 5000 {
		t.Errorf("Port = %d, want 5000", d.cfg.Port)
	}
	if d.cfg.Domain != "local." {
		t.Errorf("Domain = %s, want local.", d.cfg.Domain)
	}
}

func TestMdnsDiscoveryStartStop(t *testing.T) {
	d := NewMdnsDiscovery(MdnsConfig{
		NodeID: "test-node",
		Port:   19999, // Use high port to avoid conflicts
	})

	// Start
	err := d.Start()
	if err != nil {
		t.Fatalf("Start() error: %v", err)
	}

	// Verify running
	d.mu.RLock()
	running := d.running
	d.mu.RUnlock()
	if !running {
		t.Error("expected running = true after Start()")
	}

	// Stop
	d.Stop()

	// Verify stopped
	d.mu.RLock()
	running = d.running
	d.mu.RUnlock()
	if running {
		t.Error("expected running = false after Stop()")
	}
}

func TestMdnsDiscoveryDoubleStart(t *testing.T) {
	d := NewMdnsDiscovery(MdnsConfig{
		NodeID: "test-node",
		Port:   19998,
	})

	d.Start()
	defer d.Stop()

	// Second start should be no-op
	err := d.Start()
	if err != nil {
		t.Errorf("double Start() error: %v", err)
	}
}

func TestMdnsPeerInfo(t *testing.T) {
	peer := MdnsPeerInfo{
		NodeID:     "peer-1",
		Port:       5000,
		Version:    "1.0.0",
		PQCEnabled: true,
		Services:   []string{"mesh"},
		LastSeen:   time.Now(),
	}

	if peer.NodeID != "peer-1" {
		t.Errorf("NodeID = %s, want peer-1", peer.NodeID)
	}
	if !peer.PQCEnabled {
		t.Error("PQCEnabled should be true")
	}
}

func TestParseMDNSTxt(t *testing.T) {
	tests := []struct {
		input string
		key   string
		value string
	}{
		{"node_id=test", "node_id", "test"},
		{"version=1.0", "version", "1.0"},
		{"pqc_enabled=true", "pqc_enabled", "true"},
		{"nodelimiter", "nodelimiter", ""},
	}

	for _, tt := range tests {
		k, v := parseMDNSTxt(tt.input)
		if k != tt.key || v != tt.value {
			t.Errorf("parseMDNSTxt(%q) = (%q, %q), want (%q, %q)", tt.input, k, v, tt.key, tt.value)
		}
	}
}
