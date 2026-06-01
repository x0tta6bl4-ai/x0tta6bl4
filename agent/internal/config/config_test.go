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
	if cfg.RuntimeIdentityJWTSVIDSource != "auto" {
		t.Errorf("RuntimeIdentityJWTSVIDSource = %s, want auto", cfg.RuntimeIdentityJWTSVIDSource)
	}
	if cfg.RuntimeIdentityJWTSVIDAudience != "x0tta6bl4-maas" {
		t.Errorf("RuntimeIdentityJWTSVIDAudience = %s", cfg.RuntimeIdentityJWTSVIDAudience)
	}
	if cfg.RuntimeIdentityMeasuredAttestationProvider != "sgx" {
		t.Errorf("RuntimeIdentityMeasuredAttestationProvider = %s", cfg.RuntimeIdentityMeasuredAttestationProvider)
	}
	if cfg.RuntimeIdentityMeasuredAttestationRefreshIntervalSec != 3600 {
		t.Errorf("RuntimeIdentityMeasuredAttestationRefreshIntervalSec = %d", cfg.RuntimeIdentityMeasuredAttestationRefreshIntervalSec)
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

	yaml := "" +
		"node_id: \"test-node-42\"\n" +
		"api_endpoint: \"https://test.example.com\"\n" +
		"listen_port: 9876\n" +
		"pqc_enabled: false\n" +
		"obfuscation: xor\n" +
		"log_level: debug\n" +
		"heartbeat_interval_sec: 10\n" +
		"dataplane_probe_target: \"127.0.0.1\"\n" +
		"runtime_identity_binding_type: local_spiffe_hint\n" +
		"runtime_identity_spiffe_id: \"spiffe://x0tta6bl4.mesh/node/test-node-42\"\n" +
		"runtime_identity_nonce: \"stable\"\n" +
		"runtime_identity_auto_bind_verified: true\n" +
		"runtime_identity_auto_bind_jwt_svid: true\n" +
		"runtime_identity_jwt_svid_source: workload_api\n" +
		"runtime_identity_jwt_svid_audience: \"maas-test\"\n" +
		"runtime_identity_jwt_svid_file: \"/run/spire/jwt-svid.token\"\n" +
		"runtime_identity_workload_api_addr: \"unix:///run/spire/sockets/agent.sock\"\n" +
		"runtime_identity_auto_refresh_measured_attestation: true\n" +
		"runtime_identity_measured_attestation_provider: mock\n" +
		"runtime_identity_measured_attestation_report_data: \"TRUSTED_X0T\"\n" +
		"runtime_identity_measured_attestation_refresh_interval_sec: 120\n"
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
	if cfg.DataplaneProbeTarget != "127.0.0.1" {
		t.Errorf("DataplaneProbeTarget = %s, want 127.0.0.1", cfg.DataplaneProbeTarget)
	}
	if cfg.RuntimeIdentityBindingType != "local_spiffe_hint" {
		t.Errorf("RuntimeIdentityBindingType = %s", cfg.RuntimeIdentityBindingType)
	}
	if cfg.RuntimeIdentitySpiffeID != "spiffe://x0tta6bl4.mesh/node/test-node-42" {
		t.Errorf("RuntimeIdentitySpiffeID = %s", cfg.RuntimeIdentitySpiffeID)
	}
	if cfg.RuntimeIdentityNonce != "stable" {
		t.Errorf("RuntimeIdentityNonce = %s", cfg.RuntimeIdentityNonce)
	}
	if !cfg.RuntimeIdentityAutoBindVerified {
		t.Error("RuntimeIdentityAutoBindVerified should be true")
	}
	if !cfg.RuntimeIdentityAutoBindJWTSVID {
		t.Error("RuntimeIdentityAutoBindJWTSVID should be true")
	}
	if cfg.RuntimeIdentityJWTSVIDSource != "workload_api" {
		t.Errorf("RuntimeIdentityJWTSVIDSource = %s", cfg.RuntimeIdentityJWTSVIDSource)
	}
	if cfg.RuntimeIdentityJWTSVIDAudience != "maas-test" {
		t.Errorf("RuntimeIdentityJWTSVIDAudience = %s", cfg.RuntimeIdentityJWTSVIDAudience)
	}
	if cfg.RuntimeIdentityJWTSVIDFile != "/run/spire/jwt-svid.token" {
		t.Errorf("RuntimeIdentityJWTSVIDFile = %s", cfg.RuntimeIdentityJWTSVIDFile)
	}
	if cfg.RuntimeIdentityWorkloadAPIAddr != "unix:///run/spire/sockets/agent.sock" {
		t.Errorf("RuntimeIdentityWorkloadAPIAddr = %s", cfg.RuntimeIdentityWorkloadAPIAddr)
	}
	if !cfg.RuntimeIdentityAutoRefreshMeasuredAttestation {
		t.Error("RuntimeIdentityAutoRefreshMeasuredAttestation should be true")
	}
	if cfg.RuntimeIdentityMeasuredAttestationProvider != "mock" {
		t.Errorf("RuntimeIdentityMeasuredAttestationProvider = %s", cfg.RuntimeIdentityMeasuredAttestationProvider)
	}
	if cfg.RuntimeIdentityMeasuredAttestationReportData != "TRUSTED_X0T" {
		t.Errorf("RuntimeIdentityMeasuredAttestationReportData = %s", cfg.RuntimeIdentityMeasuredAttestationReportData)
	}
	if cfg.RuntimeIdentityMeasuredAttestationRefreshIntervalSec != 120 {
		t.Errorf("RuntimeIdentityMeasuredAttestationRefreshIntervalSec = %d", cfg.RuntimeIdentityMeasuredAttestationRefreshIntervalSec)
	}
}

func TestLoadFromFile_InvalidYAML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bad.yaml")
	// YAML v3 is lenient; use truly broken content
	os.WriteFile(path, []byte("listen_port: [unterminated"), 0644)

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
	t.Setenv("X0T_MESH_ID", "mesh-env")
	t.Setenv("X0T_DATAPLANE_PROBE_TARGET", "192.0.2.10")
	t.Setenv("X0T_LOG_LEVEL", "debug")
	t.Setenv("X0T_PQC_ENABLED", "false")
	t.Setenv("X0T_RUNTIME_IDENTITY_BINDING_TYPE", "measured_attestation")
	t.Setenv("X0T_RUNTIME_IDENTITY_ATTESTATION_DIGEST", "sha256:abc123")
	t.Setenv("X0T_RUNTIME_IDENTITY_NONCE", "env-stable")
	t.Setenv("X0T_RUNTIME_IDENTITY_AUTO_BIND_VERIFIED", "true")
	t.Setenv("X0T_RUNTIME_IDENTITY_AUTO_BIND_JWT_SVID", "true")
	t.Setenv("X0T_RUNTIME_IDENTITY_JWT_SVID_SOURCE", "workload_api")
	t.Setenv("X0T_RUNTIME_IDENTITY_JWT_SVID_AUDIENCE", "env-audience")
	t.Setenv("X0T_RUNTIME_IDENTITY_JWT_SVID_FILE", "/run/spire/env-jwt-svid.token")
	t.Setenv("X0T_RUNTIME_IDENTITY_WORKLOAD_API_ADDR", "unix:///run/spire/env.sock")
	t.Setenv("X0T_RUNTIME_IDENTITY_AUTO_REFRESH_MEASURED_ATTESTATION", "true")
	t.Setenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_PROVIDER", "mock")
	t.Setenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_REPORT_DATA", "TRUSTED_X0T_ENV")
	t.Setenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_REPORT_FILE", "/tmp/report.bin")
	t.Setenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_QUOTE_FILE", "/tmp/quote.bin")
	t.Setenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_SIGNATURE_FILE", "/tmp/signature.bin")
	t.Setenv("X0T_RUNTIME_IDENTITY_MEASURED_ATTESTATION_REFRESH_INTERVAL_SEC", "180")

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
	if cfg.MeshID != "mesh-env" {
		t.Errorf("MeshID = %s, want mesh-env", cfg.MeshID)
	}
	if cfg.DataplaneProbeTarget != "192.0.2.10" {
		t.Errorf("DataplaneProbeTarget = %s, want 192.0.2.10", cfg.DataplaneProbeTarget)
	}
	if cfg.PQCEnabled {
		t.Error("PQCEnabled should be overridden to false")
	}
	if cfg.RuntimeIdentityBindingType != "measured_attestation" {
		t.Errorf("RuntimeIdentityBindingType = %s", cfg.RuntimeIdentityBindingType)
	}
	if cfg.RuntimeIdentityAttestationDigest != "sha256:abc123" {
		t.Errorf("RuntimeIdentityAttestationDigest = %s", cfg.RuntimeIdentityAttestationDigest)
	}
	if cfg.RuntimeIdentityNonce != "env-stable" {
		t.Errorf("RuntimeIdentityNonce = %s", cfg.RuntimeIdentityNonce)
	}
	if !cfg.RuntimeIdentityAutoBindVerified {
		t.Error("RuntimeIdentityAutoBindVerified should be true")
	}
	if !cfg.RuntimeIdentityAutoBindJWTSVID {
		t.Error("RuntimeIdentityAutoBindJWTSVID should be true")
	}
	if cfg.RuntimeIdentityJWTSVIDSource != "workload_api" {
		t.Errorf("RuntimeIdentityJWTSVIDSource = %s", cfg.RuntimeIdentityJWTSVIDSource)
	}
	if cfg.RuntimeIdentityJWTSVIDAudience != "env-audience" {
		t.Errorf("RuntimeIdentityJWTSVIDAudience = %s", cfg.RuntimeIdentityJWTSVIDAudience)
	}
	if cfg.RuntimeIdentityJWTSVIDFile != "/run/spire/env-jwt-svid.token" {
		t.Errorf("RuntimeIdentityJWTSVIDFile = %s", cfg.RuntimeIdentityJWTSVIDFile)
	}
	if cfg.RuntimeIdentityWorkloadAPIAddr != "unix:///run/spire/env.sock" {
		t.Errorf("RuntimeIdentityWorkloadAPIAddr = %s", cfg.RuntimeIdentityWorkloadAPIAddr)
	}
	if !cfg.RuntimeIdentityAutoRefreshMeasuredAttestation {
		t.Error("RuntimeIdentityAutoRefreshMeasuredAttestation should be true")
	}
	if cfg.RuntimeIdentityMeasuredAttestationProvider != "mock" {
		t.Errorf("RuntimeIdentityMeasuredAttestationProvider = %s", cfg.RuntimeIdentityMeasuredAttestationProvider)
	}
	if cfg.RuntimeIdentityMeasuredAttestationReportData != "TRUSTED_X0T_ENV" {
		t.Errorf("RuntimeIdentityMeasuredAttestationReportData = %s", cfg.RuntimeIdentityMeasuredAttestationReportData)
	}
	if cfg.RuntimeIdentityMeasuredAttestationReportFile != "/tmp/report.bin" {
		t.Errorf("RuntimeIdentityMeasuredAttestationReportFile = %s", cfg.RuntimeIdentityMeasuredAttestationReportFile)
	}
	if cfg.RuntimeIdentityMeasuredAttestationQuoteFile != "/tmp/quote.bin" {
		t.Errorf("RuntimeIdentityMeasuredAttestationQuoteFile = %s", cfg.RuntimeIdentityMeasuredAttestationQuoteFile)
	}
	if cfg.RuntimeIdentityMeasuredAttestationSignatureFile != "/tmp/signature.bin" {
		t.Errorf("RuntimeIdentityMeasuredAttestationSignatureFile = %s", cfg.RuntimeIdentityMeasuredAttestationSignatureFile)
	}
	if cfg.RuntimeIdentityMeasuredAttestationRefreshIntervalSec != 180 {
		t.Errorf("RuntimeIdentityMeasuredAttestationRefreshIntervalSec = %d", cfg.RuntimeIdentityMeasuredAttestationRefreshIntervalSec)
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

func TestValidate_RuntimeIdentityBinding(t *testing.T) {
	cfg := DefaultConfig()
	cfg.RuntimeIdentityBindingType = "local_spiffe_hint"
	if err := cfg.Validate(); err == nil {
		t.Error("expected error without runtime_identity_spiffe_id")
	}

	cfg.RuntimeIdentitySpiffeID = "spiffe://x0tta6bl4.mesh/node/test"
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected valid local_spiffe_hint binding, got %v", err)
	}

	cfg.RuntimeIdentityBindingType = "verified_spiffe_svid"
	if err := cfg.Validate(); err == nil {
		t.Error("expected verified_spiffe_svid to require an attestation digest")
	}
	cfg.RuntimeIdentityAttestationDigest = "sha256:trusted-svid"
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected valid verified_spiffe_svid binding, got %v", err)
	}

	cfg.RuntimeIdentityBindingType = "verified_jwt_svid"
	cfg.RuntimeIdentityAttestationDigest = ""
	if err := cfg.Validate(); err == nil {
		t.Error("expected verified_jwt_svid to require an attestation digest")
	}
	cfg.RuntimeIdentityAttestationDigest = "jwt-svid:trusted"
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected valid verified_jwt_svid binding, got %v", err)
	}

	cfg.RuntimeIdentityAutoBindJWTSVID = true
	cfg.RuntimeIdentityJWTSVIDSource = "file"
	if err := cfg.Validate(); err == nil {
		t.Error("expected file JWT-SVID source to require runtime_identity_jwt_svid_file")
	}
	cfg.RuntimeIdentityJWTSVIDFile = "/run/spire/jwt-svid.token"
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected valid file JWT-SVID bind, got %v", err)
	}
	cfg.RuntimeIdentityJWTSVIDSource = "workload_api"
	cfg.RuntimeIdentityJWTSVIDFile = ""
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected valid Workload API JWT-SVID bind without file, got %v", err)
	}
	cfg.RuntimeIdentityJWTSVIDSource = "invalid"
	if err := cfg.Validate(); err == nil {
		t.Error("expected invalid JWT-SVID source to fail")
	}

	cfg = DefaultConfig()
	cfg.RuntimeIdentityAutoRefreshMeasuredAttestation = true
	cfg.RuntimeIdentityMeasuredAttestationProvider = "mock"
	if err := cfg.Validate(); err == nil {
		t.Error("expected measured attestation refresh to require report data")
	}
	cfg.RuntimeIdentityMeasuredAttestationReportData = "TRUSTED_X0T"
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected valid mock measured attestation refresh, got %v", err)
	}
	cfg.RuntimeIdentityMeasuredAttestationProvider = "sgx"
	if err := cfg.Validate(); err == nil {
		t.Error("expected sgx measured attestation refresh to require quote/signature files")
	}
	cfg.RuntimeIdentityMeasuredAttestationQuoteFile = "/run/x0t/quote.bin"
	cfg.RuntimeIdentityMeasuredAttestationSignatureFile = "/run/x0t/signature.bin"
	if err := cfg.Validate(); err != nil {
		t.Errorf("expected valid sgx measured attestation refresh, got %v", err)
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
