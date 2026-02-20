package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	if cfg.ListenPort != 5000 {
		t.Errorf("ListenPort = %d, want 5000", cfg.ListenPort)
	}
	if cfg.MulticastGroup != "239.255.77.77" {
		t.Errorf("MulticastGroup = %s, want 239.255.77.77", cfg.MulticastGroup)
	}
	if cfg.MulticastPort != 7777 {
		t.Errorf("MulticastPort = %d, want 7777", cfg.MulticastPort)
	}
	if !cfg.PQCEnabled {
		t.Error("PQCEnabled should default to true")
	}
	if cfg.Obfuscation != "none" {
		t.Errorf("Obfuscation = %s, want none", cfg.Obfuscation)
	}
	if cfg.HeartbeatIntervalSec != 30 {
		t.Errorf("HeartbeatIntervalSec = %d, want 30", cfg.HeartbeatIntervalSec)
	}
	if cfg.LogLevel != "info" {
		t.Errorf("LogLevel = %s, want info", cfg.LogLevel)
	}
}

func TestLoadFromFile_Defaults(t *testing.T) {
	cfg, err := LoadFromFile("/nonexistent/path.yaml")
	if err != nil {
		t.Fatalf("LoadFromFile should return defaults for missing file, got error: %v", err)
	}
	if cfg.ListenPort != DefaultListenPort {
		t.Errorf("expected default ListenPort %d, got %d", DefaultListenPort, cfg.ListenPort)
	}
}

func TestLoadFromFile_ValidYAML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "agent.yaml")

	yaml := `
node_id: "test-node-42"
api_endpoint: "https://test.example.com"
listen_port: 9876
pqc_enabled: false
obfuscation: xor
log_level: debug
heartbeat_interval_sec: 10
`
	if err := os.WriteFile(path, []byte(yaml), 0644); err != nil {
		t.Fatal(err)
	}

	cfg, err := LoadFromFile(path)
	if err != nil {
		t.Fatalf("LoadFromFile: %v", err)
	}
	if cfg.NodeID != "test-node-42" {
		t.Errorf("NodeID = %s, want test-node-42", cfg.NodeID)
	}
	if cfg.APIEndpoint != "https://test.example.com" {
		t.Errorf("APIEndpoint = %s", cfg.APIEndpoint)
	}
	if cfg.ListenPort != 9876 {
		t.Errorf("ListenPort = %d, want 9876", cfg.ListenPort)
	}
	if cfg.PQCEnabled {
		t.Error("PQCEnabled should be false")
	}
	if cfg.Obfuscation != "xor" {
		t.Errorf("Obfuscation = %s, want xor", cfg.Obfuscation)
	}
	if cfg.HeartbeatIntervalSec != 10 {
		t.Errorf("HeartbeatIntervalSec = %d, want 10", cfg.HeartbeatIntervalSec)
	}
}

func TestLoadFromFile_InvalidYAML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bad.yaml")
	os.WriteFile(path, []byte(":::invalid:::"), 0644)

	_, err := LoadFromFile(path)
	if err == nil {
		t.Fatal("expected error for invalid YAML")
	}
}

func TestEnvOverrides(t *testing.T) {
	cfg := DefaultConfig()

	t.Setenv("X0T_NODE_ID", "env-node")
	t.Setenv("X0T_API_ENDPOINT", "https://env.example.com")
	t.Setenv("X0T_JOIN_TOKEN", "secret-token")
	t.Setenv("X0T_LOG_LEVEL", "debug")
	t.Setenv("X0T_PQC_ENABLED", "false")

	cfg.ApplyEnvOverrides()

	if cfg.NodeID != "env-node" {
		t.Errorf("NodeID = %s, want env-node", cfg.NodeID)
	}
	if cfg.APIEndpoint != "https://env.example.com" {
		t.Errorf("APIEndpoint = %s", cfg.APIEndpoint)
	}
	if cfg.JoinToken != "secret-token" {
		t.Errorf("JoinToken = %s", cfg.JoinToken)
	}
	if cfg.PQCEnabled {
		t.Error("PQCEnabled should be overridden to false")
	}
}

func TestValidate_Valid(t *testing.T) {
	cfg := DefaultConfig()
	if err := cfg.Validate(); err != nil {
		t.Errorf("default config should be valid: %v", err)
	}
}

func TestValidate_BadPort(t *testing.T) {
	cfg := DefaultConfig()
	cfg.ListenPort = 0
	if err := cfg.Validate(); err == nil {
		t.Error("expected error for port 0")
	}

	cfg.ListenPort = 99999
	if err := cfg.Validate(); err == nil {
		t.Error("expected error for port 99999")
	}
}

func TestValidate_BadObfuscation(t *testing.T) {
	cfg := DefaultConfig()
	cfg.Obfuscation = "invalid"
	if err := cfg.Validate(); err == nil {
		t.Error("expected error for invalid obfuscation")
	}
}

func TestValidate_BadTrafficProfile(t *testing.T) {
	cfg := DefaultConfig()
	cfg.TrafficProfile = "torrent"
	if err := cfg.Validate(); err == nil {
		t.Error("expected error for invalid traffic profile")
	}
}

func TestSaveAndReload(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "saved.yaml")

	orig := DefaultConfig()
	orig.NodeID = "save-test"
	orig.ListenPort = 4242
	orig.PQCEnabled = false

	if err := orig.SaveToFile(path); err != nil {
		t.Fatalf("SaveToFile: %v", err)
	}

	loaded, err := LoadFromFile(path)
	if err != nil {
		t.Fatalf("LoadFromFile: %v", err)
	}

	if loaded.NodeID != "save-test" {
		t.Errorf("NodeID = %s, want save-test", loaded.NodeID)
	}
	if loaded.ListenPort != 4242 {
		t.Errorf("ListenPort = %d, want 4242", loaded.ListenPort)
	}
	if loaded.PQCEnabled {
		t.Error("PQCEnabled should be false after reload")
	}
}
