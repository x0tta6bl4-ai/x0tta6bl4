// Package config handles agent configuration from YAML/env/CLI.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
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
	RuntimeCredential          string `yaml:"runtime_credential,omitempty"`            // assigned after registration
	RuntimeCredentialExpiresAt string `yaml:"runtime_credential_expires_at,omitempty"` // assigned after registration

	// Networking
	ListenPort           int    `yaml:"listen_port"`            // mesh data port (default 5000)
	BindAddr             string `yaml:"bind_addr"`              // default "0.0.0.0"
	DataplaneProbeTarget string `yaml:"dataplane_probe_target"` // optional post-heal probe target

	// Discovery
	MulticastGroup string   `yaml:"multicast_group"` // default 239.255.77.77
	MulticastPort  int      `yaml:"multicast_port"`  // default 7777
	BootstrapNodes []string `yaml:"bootstrap_nodes"` // ["host:port", ...]

	// Security
	PQCEnabled                                           bool   `yaml:"pqc_enabled"`                                                // default true
	Obfuscation                                          string `yaml:"obfuscation"`                                                // none|xor|aes
	RuntimeIdentityBindingType                           string `yaml:"runtime_identity_binding_type"`                              // optional local_spiffe_hint|spiffe_svid_digest|verified_jwt_svid|measured_attestation
	RuntimeIdentitySpiffeID                              string `yaml:"runtime_identity_spiffe_id"`                                 // optional SPIFFE ID hint for bound rotation
	RuntimeIdentityAttestationDigest                     string `yaml:"runtime_identity_attestation_digest"`                        // optional SVID/attestation digest
	RuntimeIdentityNonce                                 string `yaml:"runtime_identity_nonce"`                                     // optional stable binding nonce
	RuntimeIdentityAutoBindVerified                      bool   `yaml:"runtime_identity_auto_bind_verified"`                        // opt-in trusted proxy bind attempt
	RuntimeIdentityAutoBindJWTSVID                       bool   `yaml:"runtime_identity_auto_bind_jwt_svid"`                        // opt-in API-side JWT-SVID bind attempt
	RuntimeIdentityJWTSVIDSource                         string `yaml:"runtime_identity_jwt_svid_source"`                           // auto|workload_api|file
	RuntimeIdentityJWTSVIDAudience                       string `yaml:"runtime_identity_jwt_svid_audience"`                         // JWT-SVID audience expected by MaaS
	RuntimeIdentityJWTSVIDFile                           string `yaml:"runtime_identity_jwt_svid_file"`                             // optional file containing a live JWT-SVID
	RuntimeIdentityWorkloadAPIAddr                       string `yaml:"runtime_identity_workload_api_addr"`                         // optional SPIFFE Workload API socket URI
	RuntimeIdentityAutoRefreshMeasuredAttestation        bool   `yaml:"runtime_identity_auto_refresh_measured_attestation"`         // opt-in TEE attestation refresh
	RuntimeIdentityMeasuredAttestationProvider           string `yaml:"runtime_identity_measured_attestation_provider"`             // mock|sgx
	RuntimeIdentityMeasuredAttestationReportData         string `yaml:"runtime_identity_measured_attestation_report_data"`          // optional UTF-8 report data
	RuntimeIdentityMeasuredAttestationReportFile         string `yaml:"runtime_identity_measured_attestation_report_file"`          // optional binary report data file
	RuntimeIdentityMeasuredAttestationQuoteFile          string `yaml:"runtime_identity_measured_attestation_quote_file"`           // optional binary quote file
	RuntimeIdentityMeasuredAttestationSignatureFile      string `yaml:"runtime_identity_measured_attestation_signature_file"`       // optional binary signature file
	RuntimeIdentityMeasuredAttestationRefreshIntervalSec int    `yaml:"runtime_identity_measured_attestation_refresh_interval_sec"` // default 3600

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
		APIEndpoint:                    DefaultAPIURL,
		ListenPort:                     DefaultListenPort,
		BindAddr:                       "0.0.0.0",
		MulticastGroup:                 "239.255.77.77",
		MulticastPort:                  7777,
		PQCEnabled:                     true,
		Obfuscation:                    "none",
		RuntimeIdentityJWTSVIDSource:   "auto",
		RuntimeIdentityJWTSVIDAudience: "x0tta6bl4-maas",
		RuntimeIdentityMeasuredAttestationProvider:           "sgx",
		RuntimeIdentityMeasuredAttestationRefreshIntervalSec: 3600,
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
	if v := os.Getenv("X0T_DATAPLANE_PROBE_TARGET"); v != "" {
		c.DataplaneProbeTarget = v
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
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_BINDING_TYPE"); v != "" {
		c.RuntimeIdentityBindingType = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_SPIFFE_ID"); v != "" {
		c.RuntimeIdentitySpiffeID = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_ATTESTATION_DIGEST"); v != "" {
		c.RuntimeIdentityAttestationDigest = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_NONCE"); v != "" {
		c.RuntimeIdentityNonce = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_AUTO_BIND_VERIFIED"); strings.ToLower(v) == "true" {
		c.RuntimeIdentityAutoBindVerified = true
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_AUTO_BIND_JWT_SVID"); strings.ToLower(v) == "true" {
		c.RuntimeIdentityAutoBindJWTSVID = true
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_JWT_SVID_SOURCE"); v != "" {
		c.RuntimeIdentityJWTSVIDSource = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_JWT_SVID_AUDIENCE"); v != "" {
		c.RuntimeIdentityJWTSVIDAudience = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_JWT_SVID_FILE"); v != "" {
		c.RuntimeIdentityJWTSVIDFile = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_WORKLOAD_API_ADDR"); v != "" {
		c.RuntimeIdentityWorkloadAPIAddr = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_AUTO_REFRESH_MEASURED_ATTESTATION"); strings.ToLower(v) == "true" {
		c.RuntimeIdentityAutoRefreshMeasuredAttestation = true
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_PROVIDER"); v != "" {
		c.RuntimeIdentityMeasuredAttestationProvider = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_REPORT_DATA"); v != "" {
		c.RuntimeIdentityMeasuredAttestationReportData = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_REPORT_FILE"); v != "" {
		c.RuntimeIdentityMeasuredAttestationReportFile = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_QUOTE_FILE"); v != "" {
		c.RuntimeIdentityMeasuredAttestationQuoteFile = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_SIGNATURE_FILE"); v != "" {
		c.RuntimeIdentityMeasuredAttestationSignatureFile = v
	}
	if v := os.Getenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_REFRESH_INTERVAL_SEC"); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil {
			c.RuntimeIdentityMeasuredAttestationRefreshIntervalSec = parsed
		}
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

	bindingType := strings.TrimSpace(c.RuntimeIdentityBindingType)
	if bindingType != "" {
		validBindingType := map[string]bool{
			"local_spiffe_hint":    true,
			"spiffe_svid_digest":   true,
			"verified_spiffe_svid": true,
			"verified_jwt_svid":    true,
			"measured_attestation": true,
		}
		if !validBindingType[bindingType] {
			return fmt.Errorf("invalid runtime_identity_binding_type: %s", bindingType)
		}
		if bindingType == "local_spiffe_hint" && strings.TrimSpace(c.RuntimeIdentitySpiffeID) == "" {
			return fmt.Errorf("runtime_identity_spiffe_id is required for local_spiffe_hint")
		}
		if bindingType == "measured_attestation" && strings.TrimSpace(c.RuntimeIdentityAttestationDigest) == "" {
			return fmt.Errorf("runtime_identity_attestation_digest is required for measured_attestation")
		}
		if bindingType == "spiffe_svid_digest" &&
			(strings.TrimSpace(c.RuntimeIdentitySpiffeID) == "" ||
				strings.TrimSpace(c.RuntimeIdentityAttestationDigest) == "") {
			return fmt.Errorf("runtime_identity_spiffe_id and runtime_identity_attestation_digest are required for spiffe_svid_digest")
		}
		if bindingType == "verified_spiffe_svid" &&
			(strings.TrimSpace(c.RuntimeIdentitySpiffeID) == "" ||
				strings.TrimSpace(c.RuntimeIdentityAttestationDigest) == "") {
			return fmt.Errorf("runtime_identity_spiffe_id and runtime_identity_attestation_digest are required for verified_spiffe_svid rotation proof")
		}
		if bindingType == "verified_jwt_svid" &&
			(strings.TrimSpace(c.RuntimeIdentitySpiffeID) == "" ||
				strings.TrimSpace(c.RuntimeIdentityAttestationDigest) == "") {
			return fmt.Errorf("runtime_identity_spiffe_id and runtime_identity_attestation_digest are required for verified_jwt_svid rotation proof")
		}
	}
	if c.RuntimeIdentityAutoBindJWTSVID && strings.TrimSpace(c.RuntimeIdentityJWTSVIDFile) == "" {
		source := strings.ToLower(strings.TrimSpace(c.RuntimeIdentityJWTSVIDSource))
		if source == "" {
			source = "auto"
		}
		if source == "file" {
			return fmt.Errorf("runtime_identity_jwt_svid_file is required when runtime_identity_jwt_svid_source is file")
		}
		if source != "auto" && source != "workload_api" {
			return fmt.Errorf("invalid runtime_identity_jwt_svid_source: %s", source)
		}
	}
	if source := strings.ToLower(strings.TrimSpace(c.RuntimeIdentityJWTSVIDSource)); source != "" {
		validSource := map[string]bool{"auto": true, "file": true, "workload_api": true}
		if !validSource[source] {
			return fmt.Errorf("invalid runtime_identity_jwt_svid_source: %s", source)
		}
	}
	if c.RuntimeIdentityMeasuredAttestationRefreshIntervalSec <= 0 {
		return fmt.Errorf("runtime_identity_measured_attestation_refresh_interval_sec must be positive")
	}
	if c.RuntimeIdentityAutoRefreshMeasuredAttestation {
		provider := strings.ToLower(strings.TrimSpace(c.RuntimeIdentityMeasuredAttestationProvider))
		if provider == "" {
			return fmt.Errorf("runtime_identity_measured_attestation_provider is required when measured attestation refresh is enabled")
		}
		validProvider := map[string]bool{"mock": true, "sgx": true}
		if !validProvider[provider] {
			return fmt.Errorf("invalid runtime_identity_measured_attestation_provider: %s", provider)
		}
		if strings.TrimSpace(c.RuntimeIdentityMeasuredAttestationReportData) == "" &&
			strings.TrimSpace(c.RuntimeIdentityMeasuredAttestationReportFile) == "" {
			return fmt.Errorf("measured attestation refresh requires report data or report file")
		}
		if provider == "sgx" &&
			(strings.TrimSpace(c.RuntimeIdentityMeasuredAttestationQuoteFile) == "" ||
				strings.TrimSpace(c.RuntimeIdentityMeasuredAttestationSignatureFile) == "") {
			return fmt.Errorf("sgx measured attestation refresh requires quote and signature files")
		}
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
