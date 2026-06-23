package actuator

import (
	"errors"
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"time"
)

// Whitelists for security
var (
	AllowedServices = map[string]bool{
		"x-ui.service":      true,
		"ghost-vpn.service": true,
		"nginx.service":     true,
	}
	AllowedConfigFiles = map[string]bool{
		"/usr/local/etc/xray/config.json": true,
		"/usr/local/x-ui/bin/config.json": true,
	}
)

// CommandHandler is a function that executes a specific allowed action.
type CommandHandler func(target string, params map[string]string) error

// Executor securely applies the AI's action plan.
type Executor struct {
	allowedCommands map[string]CommandHandler
	snapshots       *SnapshotManager
}

func NewExecutor() *Executor {
	e := &Executor{
		allowedCommands: make(map[string]CommandHandler),
		snapshots:       NewSnapshotManager(),
	}

	// Register whitelisted commands
	e.allowedCommands["restart_service"] = e.safeRestartService
	e.allowedCommands["patch_config"] = e.safePatchConfig

	return e
}

// ApplyPlan safely executes the plan and rolls back on failure.
func (e *Executor) ApplyPlan(plan *ActionPlan) error {
	log.Printf("[Executor] Applying AI Diagnosis: %s\n", plan.Diagnosis)

	var activeSnapshots []string

	// Defer rollback for all taken snapshots in case of a panic
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[Executor] CRITICAL: Panic occurred during execution: %v. Rolling back...", r)
			e.rollbackAll(activeSnapshots)
		}
	}()

	for _, action := range plan.Actions {
		handler, exists := e.allowedCommands[action.Command]
		if !exists {
			err := fmt.Errorf("security violation: unknown command %q", action.Command)
			e.rollbackAll(activeSnapshots)
			return err
		}

		// Create snapshot before modifying
		snapID := e.snapshots.CreateSnapshot(action.Target)
		if snapID != "" {
			activeSnapshots = append(activeSnapshots, snapID)
		}

		log.Printf("[Executor] Executing command: %s on target: %s\n", action.Command, action.Target)
		if err := handler(action.Target, action.Params); err != nil {
			log.Printf("[Executor] Command failed: %v. Initiating Rollback...", err)
			e.rollbackAll(activeSnapshots)
			return err
		}
	}

	// Verify health
	if !e.verifyNetworkHealth() {
		log.Println("[Executor] Health check failed after AI patch. Initiating Rollback.")
		e.rollbackAll(activeSnapshots)
		return errors.New("applied changes broke the network")
	}

	log.Println("[Executor] AI Recovery successful.")
	for _, snapID := range activeSnapshots {
		e.snapshots.Cleanup(snapID)
	}

	return nil
}

func (e *Executor) rollbackAll(snapshots []string) {
	log.Printf("[Executor] Rolling back %d actions in reverse order...\n", len(snapshots))
	for i := len(snapshots) - 1; i >= 0; i-- {
		e.snapshots.Rollback(snapshots[i])
	}
}

// verifyNetworkHealth runs a post-action probe
func (e *Executor) verifyNetworkHealth() bool {
	log.Println("[Executor] Running post-action network probe...")

	// Test connectivity to a reliable target
	client := http.Client{
		Timeout: 5 * time.Second,
	}

	// We check if we can reach a public API.
	// In a real VPN scenario, we'd specifically check if the tunnel is passing traffic.
	resp, err := client.Get("https://api.ipify.org")
	if err != nil {
		log.Printf("[Executor] Probe FAILED: %v\n", err)
		return false
	}
	defer resp.Body.Close()

	log.Printf("[Executor] Probe OK (Status: %s)\n", resp.Status)
	return true
}

// Whitelisted Command Implementations

func (e *Executor) safeRestartService(target string, params map[string]string) error {
	if !AllowedServices[target] {
		return fmt.Errorf("security violation: service %q is not in the whitelist", target)
	}

	log.Printf("[Command] Restarting systemd service: %s\n", target)
	cmd := exec.Command("systemctl", "restart", target)
	return cmd.Run()
}

func (e *Executor) safePatchConfig(target string, params map[string]string) error {
	if !AllowedConfigFiles[target] {
		return fmt.Errorf("security violation: config file %q is not in the whitelist", target)
	}

	log.Printf("[Command] Patching config: %s with params: %v (Logic pending implementation)\n", target, params)
	// Real implementation would involve reading JSON, applying patches, and writing back.
	return nil
}
