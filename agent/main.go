// x0t-agent — Headless Mesh Agent for x0tta6bl4 MaaS platform.
// Data Plane binary. Runs as systemd service, headless, no UI.
//
// Usage:
//
//	x0t-agent --token <JOIN_TOKEN> --api-url https://maas.x0tta6bl4.io
//	x0t-agent --config /etc/x0t/agent.yaml
package main

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"syscall"
	"time"

	"github.com/x0tta6bl4/agent/internal/api"
	"github.com/x0tta6bl4/agent/internal/config"
	"github.com/x0tta6bl4/agent/internal/crypto/pqc"
	"github.com/x0tta6bl4/agent/internal/healing"
	"github.com/x0tta6bl4/agent/internal/identity"
	"github.com/x0tta6bl4/agent/internal/mesh"
	"github.com/x0tta6bl4/agent/internal/mesh/discovery"
	"github.com/x0tta6bl4/agent/internal/telemetry"
)

var Version = "dev"

func main() {
	// CLI flags
	configPath := flag.String("config", config.DefaultConfigPath, "path to config file")
	token := flag.String("token", "", "mesh join token")
	apiURL := flag.String("api-url", "", "control plane API URL")
	port := flag.Int("port", 0, "listen port (0 to use config default)")
	logLevel := flag.String("log-level", "", "log level (debug/info/warn/error)")
	showVersion := flag.Bool("version", false, "show version and exit")
	flag.Parse()

	if *showVersion {
		fmt.Printf("x0t-agent %s (%s/%s)\n", Version, runtime.GOOS, runtime.GOARCH)
		os.Exit(0)
	}

	// Load config
	cfg, err := config.LoadFromFile(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
		os.Exit(1)
	}

	// CLI overrides
	if *token != "" {
		cfg.JoinToken = *token
	}
	if *apiURL != "" {
		cfg.APIEndpoint = *apiURL
	}
	if *port > 0 {
		cfg.ListenPort = *port
	}
	if *logLevel != "" {
		cfg.LogLevel = *logLevel
	}

	// Env overrides
	cfg.ApplyEnvOverrides()

	// Generate node ID if not set
	if cfg.NodeID == "" {
		b := make([]byte, 4)
		rand.Read(b)
		cfg.NodeID = fmt.Sprintf("x0t-%s", hex.EncodeToString(b))
	}

	// Validate
	if err := cfg.Validate(); err != nil {
		fmt.Fprintf(os.Stderr, "CONFIG ERROR: %v\n", err)
		os.Exit(1)
	}

	// Setup logging
	setupLogger(cfg.LogLevel)

	slog.Info("x0t-agent starting",
		"version", Version,
		"node_id", cfg.NodeID,
		"arch", runtime.GOARCH,
		"pqc", cfg.PQCEnabled,
	)

	// Initialize components
	agent, err := newAgent(cfg, *configPath)
	if err != nil {
		slog.Error("failed to initialize agent", "error", err)
		os.Exit(1)
	}

	// Start
	if err := agent.start(); err != nil {
		slog.Error("failed to start agent", "error", err)
		os.Exit(1)
	}

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	sig := <-sigCh
	slog.Info("shutdown signal received", "signal", sig)
	agent.stop()
	slog.Info("x0t-agent stopped")
}

// agent orchestrates all components.
type agent struct {
	cfg       *config.Config
	cfgPath   string
	node      *mesh.Node
	disc      *discovery.Discovery
	pqcMgr    *pqc.TunnelManager
	healer    *healing.Monitor
	apiClient *api.Client
	telem     *telemetry.Reporter
}

func newAgent(cfg *config.Config, cfgPath string) (*agent, error) {
	// Discovery
	disc := discovery.New(
		cfg.NodeID,
		cfg.ListenPort,
		[]string{"mesh"},
		cfg.MulticastGroup,
		cfg.MulticastPort,
	)

	// Mesh node
	node := mesh.NewNode(cfg.NodeID, cfg.ListenPort, disc)

	// PQC tunnel manager
	pqcMgr, err := pqc.NewTunnelManager(cfg.NodeID)
	if err != nil {
		return nil, fmt.Errorf("pqc init: %w", err)
	}

	// Telemetry
	telem := telemetry.NewReporter(node)

	// API client
	var apiClient *api.Client
	if cfg.JoinToken != "" {
		apiClient = api.NewClient(cfg.APIEndpoint, cfg.JoinToken)

		// Load persisted credentials if they exist
		if cfg.RuntimeCredential != "" && cfg.MeshID != "" {
			apiClient.SetNodeRuntimeCredential(cfg.RuntimeCredential, cfg.RuntimeCredentialExpiresAt)
			apiClient.SetMeshID(cfg.MeshID)
			slog.Info("loaded persisted credentials", "mesh_id", cfg.MeshID, "expires_at", cfg.RuntimeCredentialExpiresAt)
		}
	}

	// Healing monitor with executor
	var alerter healing.ControlPlaneAlerter
	if apiClient != nil {
		alerter = apiClient
	}
	healer := healing.NewMonitor(node, healing.NewMeshHealingExecutor(
		cfg.NodeID,
		node,       // PeerRemover
		node,       // DiscoveryRestarter
		alerter,    // ControlPlaneAlerter (nil if no API client)
		func() []healing.PeerEntry {
			peers := node.GetPeers()
			entries := make([]healing.PeerEntry, len(peers))
			for i, p := range peers {
				entries[i] = healing.PeerEntry{
					NodeID:  p.NodeID,
					Healthy: p.Healthy,
				}
			}
			return entries
		},
	))

	return &agent{
		cfg:       cfg,
		cfgPath:   cfgPath,
		node:      node,
		disc:      disc,
		pqcMgr:    pqcMgr,
		healer:    healer,
		apiClient: apiClient,
		telem:     telem,
	}, nil
}

func (a *agent) start() error {
	// Start mesh node (includes discovery)
	if err := a.node.Start(); err != nil {
		return fmt.Errorf("mesh node start: %w", err)
	}

	// Start self-healing
	a.healer.Start()

	// Register with Control Plane (non-blocking)
	if a.apiClient != nil {
		go a.registerAndHeartbeat()
	}

	slog.Info("agent fully started",
		"node_id", a.cfg.NodeID,
		"port", a.cfg.ListenPort,
		"pqc", a.cfg.PQCEnabled,
	)
	return nil
}

func (a *agent) stop() {
	a.healer.Stop()
	a.node.Stop()
}

func (a *agent) registerAndHeartbeat() {
	// Skip registration if we already have valid persisted credentials
	if a.apiClient.IsRegistered() {
		slog.Info("agent already registered", "mesh_id", a.cfg.MeshID)
	} else {
		// Register
		hostname, _ := os.Hostname()
		resp, err := a.apiClient.Register(api.RegistrationRequest{
			NodeID:      a.cfg.NodeID,
			MeshID:      a.cfg.MeshID,
			Token:       a.cfg.JoinToken,
			DeviceClass: "edge",
			Hostname:    hostname,
			Arch:        runtime.GOARCH,
			OS:          runtime.GOOS,
			Version:     Version,
			Services:    []string{"mesh"},
		})

		if err != nil {
			slog.Error("registration failed, will retry", "error", err)
			// Continue without registration — mesh still works P2P
		} else {
			slog.Info("registered", "mesh_id", resp.MeshID)
			a.cfg.MeshID = resp.MeshID
			a.cfg.RuntimeCredential = resp.NodeRuntimeCredential
			a.cfg.RuntimeCredentialExpiresAt = resp.NodeRuntimeCredentialExpiresAt

			// Persist credentials to disk
			if err := a.cfg.SaveToFile(a.cfgPath); err != nil {
				slog.Error("failed to persist agent config", "error", err)
			} else {
				slog.Info("agent config persisted successfully", "path", a.cfgPath)
			}
		}
	}

	readJWTSVID := func() (string, error) {
		return identity.FetchJWTSVID(context.Background(), identity.JWTSVIDConfig{
			Source:          a.cfg.RuntimeIdentityJWTSVIDSource,
			Audience:        a.cfg.RuntimeIdentityJWTSVIDAudience,
			FilePath:        a.cfg.RuntimeIdentityJWTSVIDFile,
			WorkloadAPIAddr: a.cfg.RuntimeIdentityWorkloadAPIAddr,
		})
	}

	fetchNodeConfig := func() (*api.NodeConfigResponse, error) {
		if !a.cfg.RuntimeIdentityAutoBindJWTSVID {
			return a.apiClient.FetchNodeConfig(a.cfg.MeshID, a.cfg.NodeID)
		}
		token, err := readJWTSVID()
		if err != nil {
			return nil, err
		}
		return a.apiClient.FetchNodeConfigWithJWTSVID(a.cfg.MeshID, a.cfg.NodeID, token)
	}

	sendHeartbeat := func(hb api.HeartbeatRequest) error {
		if !a.cfg.RuntimeIdentityAutoBindJWTSVID {
			return a.apiClient.SendHeartbeat(hb)
		}
		token, err := readJWTSVID()
		if err != nil {
			return err
		}
		return a.apiClient.SendHeartbeatWithJWTSVID(hb, token)
	}

	configFetched := false
	tryFetchConfig := func() {
		if configFetched || a.cfg.MeshID == "" {
			return
		}
		cfgResp, err := fetchNodeConfig()
		if err != nil {
			slog.Debug("node config fetch pending", "error", err)
			return
		}
		configFetched = true
		slog.Info("node config fetched",
			"mesh_id", cfgResp.MeshID,
			"node_id", cfgResp.NodeID,
			"policies", len(cfgResp.Policies),
			"peers", len(cfgResp.Peers),
			"enforcement", cfgResp.Enforcement,
			"global_mode", cfgResp.GlobalMode,
		)
	}

	verifiedIdentityBound := false
	jwtSVIDIdentityBound := false
	tryBindJWTSVIDIdentity := func() {
		if jwtSVIDIdentityBound || !a.cfg.RuntimeIdentityAutoBindJWTSVID || a.cfg.MeshID == "" {
			return
		}
		token, err := readJWTSVID()
		if err != nil {
			slog.Debug("JWT-SVID runtime identity bind pending", "error", err)
			return
		}
		bound, err := a.apiClient.BindJWTSVIDRuntimeIdentity(a.cfg.MeshID, a.cfg.NodeID, token)
		if err != nil {
			slog.Debug("JWT-SVID runtime identity bind pending", "error", err)
			return
		}
		jwtSVIDIdentityBound = true
		verifiedIdentityBound = true
		slog.Info("JWT-SVID runtime identity bound",
			"mesh_id", bound.MeshID,
			"node_id", bound.NodeID,
			"binding_type", bound.RuntimeIdentityBindingType,
			"source", bound.RuntimeIdentityVerificationSource,
		)
	}
	tryBindVerifiedIdentity := func() {
		if verifiedIdentityBound || !a.cfg.RuntimeIdentityAutoBindVerified || a.cfg.MeshID == "" {
			return
		}
		bound, err := a.apiClient.BindVerifiedRuntimeIdentity(a.cfg.MeshID, a.cfg.NodeID)
		if err != nil {
			slog.Debug("verified runtime identity bind pending", "error", err)
			return
		}
		verifiedIdentityBound = true
		slog.Info("verified runtime identity bound",
			"mesh_id", bound.MeshID,
			"node_id", bound.NodeID,
			"binding_type", bound.RuntimeIdentityBindingType,
			"source", bound.RuntimeIdentityVerificationSource,
		)
	}
	tryBindJWTSVIDIdentity()
	tryBindVerifiedIdentity()

	measuredAttestationLastRefresh := time.Time{}
	tryRefreshMeasuredAttestation := func(force bool) {
		if !a.cfg.RuntimeIdentityAutoRefreshMeasuredAttestation || a.cfg.MeshID == "" {
			return
		}
		interval := time.Duration(a.cfg.RuntimeIdentityMeasuredAttestationRefreshIntervalSec) * time.Second
		if interval <= 0 {
			interval = time.Hour
		}
		if !force && !measuredAttestationLastRefresh.IsZero() && time.Since(measuredAttestationLastRefresh) < interval {
			return
		}
		attestation, err := measuredAttestationDataFromConfig(a.cfg)
		if err != nil {
			slog.Debug("measured attestation refresh not configured", "error", err)
			return
		}
		bound, err := a.apiClient.RefreshMeasuredAttestationRuntimeIdentity(a.cfg.MeshID, a.cfg.NodeID, attestation)
		if err != nil {
			slog.Debug("measured attestation refresh pending", "error", err)
			return
		}
		measuredAttestationLastRefresh = time.Now()
		slog.Info("measured attestation runtime identity refreshed",
			"mesh_id", bound.MeshID,
			"node_id", bound.NodeID,
			"binding_type", bound.RuntimeIdentityBindingType,
			"source", bound.RuntimeIdentityVerificationSource,
		)
	}
	tryRefreshMeasuredAttestation(true)
	tryFetchConfig()

	tryRotateCredential := func() {
		if a.cfg.MeshID == "" || !a.apiClient.ShouldRotateNodeRuntimeCredential(5*time.Minute) {
			return
		}
		var (
			rotated *api.NodeRuntimeCredentialRotateResponse
			err     error
		)
		if a.cfg.RuntimeIdentityAutoBindJWTSVID {
			token, readErr := readJWTSVID()
			if readErr != nil {
				err = readErr
			} else {
				rotated, err = a.apiClient.RotateNodeRuntimeCredentialWithJWTSVID(
					a.cfg.MeshID,
					a.cfg.NodeID,
					24*60*60,
					token,
				)
			}
		} else {
			rotated, err = a.apiClient.RotateNodeRuntimeCredentialWithIdentityProof(
				a.cfg.MeshID,
				a.cfg.NodeID,
				24*60*60,
				runtimeIdentityProofFromConfig(a.cfg),
			)
		}
		if err != nil {
			slog.Debug("node runtime credential rotation pending", "error", err)
			return
		}
		slog.Info("node runtime credential rotated",
			"mesh_id", rotated.MeshID,
			"node_id", rotated.NodeID,
			"expires_at", rotated.NodeRuntimeCredentialExpiresAt,
		)
	}

	// Heartbeat loop
	ticker := time.NewTicker(time.Duration(a.cfg.HeartbeatIntervalSec) * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		tryBindJWTSVIDIdentity()
		tryBindVerifiedIdentity()
		tryRefreshMeasuredAttestation(false)
		tryRotateCredential()
		tryFetchConfig()

		metrics := a.telem.Collect()
		hb := api.HeartbeatRequest{
			NodeID:               a.cfg.NodeID,
			Status:               "healthy",
			State:                a.node.State.String(),
			PeersTotal:           metrics.PeersTotal,
			PeersHealthy:         metrics.PeersHealthy,
			HealthScore:          metrics.HealthScore,
			UptimeSec:            metrics.UptimeSec,
			MsgSent:              metrics.MsgSent,
			MsgRecv:              metrics.MsgRecv,
			DataplaneProbeTarget: a.cfg.DataplaneProbeTarget,
		}

		if err := sendHeartbeat(hb); err != nil {
			slog.Debug("heartbeat failed", "error", err)
		}
	}
}

func runtimeIdentityProofFromConfig(cfg *config.Config) *api.RuntimeIdentityProof {
	bindingType := strings.TrimSpace(cfg.RuntimeIdentityBindingType)
	if bindingType == "" {
		return nil
	}
	return &api.RuntimeIdentityProof{
		BindingType:       bindingType,
		SPIFFEID:          strings.TrimSpace(cfg.RuntimeIdentitySpiffeID),
		AttestationDigest: strings.TrimSpace(cfg.RuntimeIdentityAttestationDigest),
		Nonce:             strings.TrimSpace(cfg.RuntimeIdentityNonce),
	}
}

func measuredAttestationDataFromConfig(cfg *config.Config) (*api.MeasuredAttestationData, error) {
	provider := strings.TrimSpace(cfg.RuntimeIdentityMeasuredAttestationProvider)
	if provider == "" {
		provider = "sgx"
	}
	data := &api.MeasuredAttestationData{Provider: provider}
	if reportData := strings.TrimSpace(cfg.RuntimeIdentityMeasuredAttestationReportData); reportData != "" {
		data.ReportData = reportData
	}
	if path := strings.TrimSpace(cfg.RuntimeIdentityMeasuredAttestationReportFile); path != "" {
		encoded, err := readFileBase64(path)
		if err != nil {
			return nil, fmt.Errorf("read measured attestation report file: %w", err)
		}
		data.ReportDataB64 = encoded
	}
	if path := strings.TrimSpace(cfg.RuntimeIdentityMeasuredAttestationQuoteFile); path != "" {
		encoded, err := readFileBase64(path)
		if err != nil {
			return nil, fmt.Errorf("read measured attestation quote file: %w", err)
		}
		data.QuoteB64 = encoded
	}
	if path := strings.TrimSpace(cfg.RuntimeIdentityMeasuredAttestationSignatureFile); path != "" {
		encoded, err := readFileBase64(path)
		if err != nil {
			return nil, fmt.Errorf("read measured attestation signature file: %w", err)
		}
		data.SignatureB64 = encoded
	}
	if !data.IsConfigured() {
		return nil, fmt.Errorf("measured attestation data is not configured")
	}
	return data, nil
}

func readFileBase64(path string) (string, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(content), nil
}

func setupLogger(level string) {
	var logLevel slog.Level
	switch level {
	case "debug":
		logLevel = slog.LevelDebug
	case "warn":
		logLevel = slog.LevelWarn
	case "error":
		logLevel = slog.LevelError
	default:
		logLevel = slog.LevelInfo
	}

	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: logLevel,
	})
	slog.SetDefault(slog.New(handler))
}
