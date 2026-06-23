package yggdrasil

import (
	"testing"
)

func TestClientConfig(t *testing.T) {
	c := NewClient(Config{
		ConfigPath: "/tmp/test-ygg.conf",
		BinaryPath: "/usr/bin/yggdrasil",
		Peers:      []string{"tcp://89.125.1.107:9001"},
		Listen:     "tcp://0.0.0.0:9001",
	})

	if c.cfg.ConfigPath != "/tmp/test-ygg.conf" {
		t.Errorf("ConfigPath = %s", c.cfg.ConfigPath)
	}
	if c.cfg.BinaryPath != "/usr/bin/yggdrasil" {
		t.Errorf("BinaryPath = %s", c.cfg.BinaryPath)
	}
	if len(c.cfg.Peers) != 1 {
		t.Errorf("Peers len = %d, want 1", len(c.cfg.Peers))
	}
}

func TestClientNotRunning(t *testing.T) {
	c := NewClient(Config{})
	if c.IsRunning() {
		t.Error("should not be running before Start()")
	}
}

func TestParseSelfInfo(t *testing.T) {
	output := `IPv6 address: 2001:db8::1
Key: abc123
Subnet: 2001:db8::/64
Version: 0.5.0`

	info := parseSelfInfo(output)
	if info.IPv6 != "2001:db8::1" {
		t.Errorf("IPv6 = %s", info.IPv6)
	}
	if info.Key != "abc123" {
		t.Errorf("Key = %s", info.Key)
	}
	if info.Version != "0.5.0" {
		t.Errorf("Version = %s", info.Version)
	}
}

func TestGetIPv6(t *testing.T) {
	c := NewClient(Config{})
	// No self info yet
	if c.GetIPv6() != "" {
		t.Error("should return empty when no self info")
	}
}
