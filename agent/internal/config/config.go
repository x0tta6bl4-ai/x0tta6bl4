// Package config handles agent configuration from YAML/env/CLI.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

const (
	DefaultListenPort = 5000
	DefaultAPIURL     = "https://maas.x0tta6bl4.io"
	DefaultDataDir    = "/var/lib/x0t"
	DefaultConfigPath = "/etc/x0t/agent.yaml"
	DefaultLogLevel   = "info"
)

// Config defines the agent configuration.
type Config struct {
	// Node identity
	NodeID string `yaml:"node_id"` // auto-generated UUID if empty

	// Control Plane
	APIEndpoint string `yaml:"api_endpoint"` // Control Plane URL
	JoinToken   string `yaml:"join_token"`   // mesh enrollment token
	MeshID      string `yaml:"mesh_id"`      // assigned after registration

	// Networking
	ListenPort int    `yaml:"listen_port"` // mesh data port (default 5000)
	BindAddr   string `yaml:"bind_addr"`   // default "0.0.0.0"

	// Discovery
	MulticastGroup string `yaml:"multicast_group"` // default 239.255.77.77
	MulticastPort  int    `yaml:"multicast_port"`  // default 7777
	BootstrapNodes []string `yaml:"bootstrap_nodes"` // ["host:port", ...]

	// Security
	PQCEnabled bool   `yaml:"pqc_enabled"` // default true
	Obfuscation string `yaml:"obfuscation"` // none|xor|aes

	// Traffic
	TrafficProfile string `yaml:"traffic_profile"` // none|gaming|streaming|voip

	// Storage
	DataDir string `yaml:"data_dir"` // /var/lib/x0t/

	// Logging
	LogLevel string `yaml:"log_level"` // debug|info|warn|error

	// Telemetry
	HeartbeatIntervalSec int `yaml:"heartbeat_interval_sec"` // default 30
}

// DefaultConfig returns a Config with sane defaults.
func DefaultConfig() *Config {
	return &Config{
		APIEndpoint:          DefaultAPIURL,
		ListenPort:           DefaultListenPort,
		BindAddr:             "0.0.0.0",
		MulticastGroup:       "239.255.77.77",
		MulticastPort:        7777,
		PQCEnabled:           true,
		Obfuscation:          "none",
		TrafficProfile:       "none",
		DataDir:              DefaultDataDir,
		LogLevel:             DefaultLogLevel,
		HeartbeatIntervalSec: 30,
	}
}

// LoadFromFile loads configuration from a YAML file.
func LoadFromFile(path string) (*Config, error) {
	cfg := DefaultConfig()

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return cfg, nil // use defaults
		}
		return nil, fmt.Errorf("read config: %w", err)
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}

	return cfg, nil
}

// ApplyEnvOverrides applies environment variable overrides.
// Env vars: X0T_NODE_ID, X0T_API_ENDPOINT, X0T_JOIN_TOKEN, etc.
func (c *Config) ApplyEnvOverrides() {
	if v := os.Getenv("X0T_NODE_ID"); v != "" {
		c.NodeID = v
	}
	if v := os.Getenv("X0T_API_ENDPOINT"); v != "" {
		c.APIEndpoint = v
	}
	if v := os.Getenv("X0T_JOIN_TOKEN"); v != "" {
		c.JoinToken = v
	}
	if v := os.Getenv("X0T_MESH_ID"); v != "" {
		c.MeshID = v
	}
	if v := os.Getenv("X0T_LOG_LEVEL"); v != "" {
		c.LogLevel = v
	}
	if v := os.Getenv("X0T_DATA_DIR"); v != "" {
		c.DataDir = v
	}
	if v := os.Getenv("X0T_PQC_ENABLED"); strings.ToLower(v) == "false" {
		c.PQCEnabled = false
	}
}

// Validate checks that the config is valid.
func (c *Config) Validate() error {
	if c.ListenPort < 1 || c.ListenPort > 65535 {
		return fmt.Errorf("invalid listen_port: %d", c.ListenPort)
	}
	if c.MulticastPort < 1 || c.MulticastPort > 65535 {
		return fmt.Errorf("invalid multicast_port: %d", c.MulticastPort)
	}

	validObf := map[string]bool{"none": true, "xor": true, "aes": true}
	if !validObf[c.Obfuscation] {
		return fmt.Errorf("invalid obfuscation: %s (valid: none, xor, aes)", c.Obfuscation)
	}

	validTP := map[string]bool{"none": true, "gaming": true, "streaming": true, "voip": true}
	if !validTP[c.TrafficProfile] {
		return fmt.Errorf("invalid traffic_profile: %s", c.TrafficProfile)
	}

	return nil
}

// SaveToFile writes config to a YAML file.
func (c *Config) SaveToFile(path string) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}

	data, err := yaml.Marshal(c)
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}

	return os.WriteFile(path, data, 0600)
}
