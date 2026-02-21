// x0t-agent — Headless Mesh Agent for x0tta6bl4 MaaS platform.
// Data Plane binary. Runs as systemd service, headless, no UI.
//
// Usage:
//
//	x0t-agent --token <JOIN_TOKEN> --api-url https://maas.x0tta6bl4.io
//	x0t-agent --config /etc/x0t/agent.yaml
package main

import (
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"

	"github.com/x0tta6bl4/agent/internal/api"
	"github.com/x0tta6bl4/agent/internal/config"
	"github.com/x0tta6bl4/agent/internal/crypto/pqc"
	"github.com/x0tta6bl4/agent/internal/healing"
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
	agent, err := newAgent(cfg)
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
	node      *mesh.Node
	disc      *discovery.Discovery
	pqcMgr    *pqc.TunnelManager
	healer    *healing.Monitor
	apiClient *api.Client
	telem     *telemetry.Reporter
}

func newAgent(cfg *config.Config) (*agent, error) {
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

	// Healing monitor
	healer := healing.NewMonitor(node, nil) // no executor yet

	// API client
	var apiClient *api.Client
	if cfg.JoinToken != "" {
		apiClient = api.NewClient(cfg.APIEndpoint, cfg.JoinToken)
	}

	return &agent{
		cfg:       cfg,
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
	// Register
	hostname, _ := os.Hostname()
	resp, err := a.apiClient.Register(api.RegistrationRequest{
		NodeID:   a.cfg.NodeID,
		Token:    a.cfg.JoinToken,
		Hostname: hostname,
		Arch:     runtime.GOARCH,
		OS:       runtime.GOOS,
		Version:  Version,
		Services: []string{"mesh"},
	})

	if err != nil {
		slog.Error("registration failed, will retry", "error", err)
		// Continue without registration — mesh still works P2P
	} else {
		slog.Info("registered", "mesh_id", resp.MeshID)
		a.cfg.MeshID = resp.MeshID
	}

	// Heartbeat loop
	ticker := time.NewTicker(time.Duration(a.cfg.HeartbeatIntervalSec) * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		metrics := a.telem.Collect()
		hb := api.HeartbeatRequest{
			NodeID:       a.cfg.NodeID,
			State:        a.node.State.String(),
			PeersTotal:   metrics.PeersTotal,
			PeersHealthy: metrics.PeersHealthy,
			HealthScore:  metrics.HealthScore,
			UptimeSec:    metrics.UptimeSec,
			MsgSent:      metrics.MsgSent,
			MsgRecv:      metrics.MsgRecv,
		}

		if err := a.apiClient.SendHeartbeat(hb); err != nil {
			slog.Debug("heartbeat failed", "error", err)
		}
	}
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
