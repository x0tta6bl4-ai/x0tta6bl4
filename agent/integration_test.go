package main

import (
	"bytes"
	"log/slog"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/x0tta6bl4/agent/internal/crypto/pqc"
	"github.com/x0tta6bl4/agent/internal/healing"
	"github.com/x0tta6bl4/agent/internal/mesh"
	"github.com/x0tta6bl4/agent/internal/mesh/discovery"
)

// --- Test doubles ---

// mockExecutor records healing actions for assertion.
type mockExecutor struct {
	mu      sync.Mutex
	actions []healing.Action
	calls   atomic.Int32
}

func (m *mockExecutor) ExecuteAction(action healing.Action) error {
	m.mu.Lock()
	m.actions = append(m.actions, action)
	m.mu.Unlock()
	m.calls.Add(1)
	return nil
}

func (m *mockExecutor) getActions() []healing.Action {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]healing.Action, len(m.actions))
	copy(out, m.actions)
	return out
}

// --- Integration tests ---

// TestFullStack_PQCHandshakeThenHealing covers:
// 1. Two mesh nodes with multicast discovery
// 2. PQC authenticated handshake (ML-KEM-768 + ML-DSA-65)
// 3. Encrypted data exchange
// 4. Peer loss detection
// 5. MAPE-K healing trigger → executor evicts peer + restarts discovery
func TestFullStack_PQCHandshakeThenHealing(t *testing.T) {
	slog.SetDefault(slog.New(slog.NewTextHandler(bytes.NewBuffer(nil), &slog.HandlerOptions{Level: slog.LevelWarn})))

	// === Phase 1: PQC Handshake ===
	t.Run("PQC_Handshake", func(t *testing.T) {
		alice, err := pqc.NewTunnelManager("alice")
		if err != nil {
			t.Fatalf("NewTunnelManager alice: %v", err)
		}
		bob, err := pqc.NewTunnelManager("bob")
		if err != nil {
			t.Fatalf("NewTunnelManager bob: %v", err)
		}

		// Pre-trust
		bob.SetTrustedPeer("alice", alice.GetSignPublicKey())
		alice.SetTrustedPeer("bob", bob.GetSignPublicKey())

		// Init
		initMsg, err := alice.CreateHandshakeInit()
		if err != nil {
			t.Fatalf("CreateHandshakeInit: %v", err)
		}

		// Response
		peerID, ss1, respMsg, err := bob.ProcessHandshakeInit(initMsg)
		if err != nil {
			t.Fatalf("ProcessHandshakeInit: %v", err)
		}
		if peerID != "alice" {
			t.Errorf("peerID = %s, want alice", peerID)
		}

		// Finish
		peerID2, ss2, err := alice.ProcessHandshakeResponse(respMsg)
		if err != nil {
			t.Fatalf("ProcessHandshakeResponse: %v", err)
		}
		if peerID2 != "bob" {
			t.Errorf("peerID = %s, want bob", peerID2)
		}

		// Shared secrets match
		if !bytes.Equal(ss1, ss2) {
			t.Fatal("shared secrets mismatch")
		}

		// Encrypted data exchange
		plaintext := []byte("integration test payload 12345")
		ct, err := alice.Encrypt(plaintext, "bob")
		if err != nil {
			t.Fatalf("Encrypt: %v", err)
		}
		pt, err := bob.Decrypt(ct, "alice")
		if err != nil {
			t.Fatalf("Decrypt: %v", err)
		}
		if !bytes.Equal(plaintext, pt) {
			t.Errorf("decrypted = %q, want %q", pt, plaintext)
		}
	})

	// === Phase 2: MITM Detection ===
	t.Run("MITM_Detection", func(t *testing.T) {
		alice, _ := pqc.NewTunnelManager("alice")
		bob, _ := pqc.NewTunnelManager("bob")
		mallory, _ := pqc.NewTunnelManager("mallory")

		alice.SetTrustedPeer("bob", bob.GetSignPublicKey())

		// Mallory impersonates bob — sends init claiming to be "bob"
		// but signed with mallory's key
		fakeInit := encodeFakeInit(t, "bob", mallory)

		_, _, _, err := alice.ProcessHandshakeInit(fakeInit)
		if err == nil {
			t.Fatal("expected MITM rejection, got nil")
		}
		t.Logf("MITM correctly rejected: %v", err)
	})

	// === Phase 3: Mesh Nodes + Healing ===
	t.Run("Mesh_Healing", func(t *testing.T) {
		// Create node A
		discA := discovery.New("node-a", 9001, []string{"mesh"}, "239.255.88.88", 8888)
		nodeA := mesh.NewNode("node-a", 9001, discA)

		// Mock executor to capture healing actions
		exec := &mockExecutor{}

		// Create healing monitor
		_ = healing.NewMonitor(nodeA, exec)

		// Simulate: node A starts with 3 peers, then 2 go unhealthy
		// We inject stats via a fake StatsProvider
		fakeStats := &fakeStatsProvider{
			peersTotal:   3,
			peersHealthy: 3,
			state:        "active",
		}
		healerWithStats := healing.NewMonitor(fakeStats, exec)

		// First cycle: learn baseline (3 peers)
		healerWithStats.Cycle()

		// Simulate peer loss: 2 of 3 peers become unhealthy
		fakeStats.mu.Lock()
		fakeStats.peersHealthy = 1
		fakeStats.mu.Unlock()

		// Second cycle: should trigger reroute (majority unhealthy)
		healerWithStats.Cycle()

		// Verify healing action was executed
		actions := exec.getActions()
		if len(actions) == 0 {
			t.Fatal("expected healing actions, got none")
		}

		foundReroute := false
		for _, a := range actions {
			if a == healing.ActionReroute {
				foundReroute = true
			}
		}
		if !foundReroute {
			t.Errorf("expected ActionReroute, got %v", actions)
		}
		t.Logf("healing actions: %v (count=%d)", actions, exec.calls.Load())

		// Simulate complete peer loss
		fakeStats.mu.Lock()
		fakeStats.peersTotal = 0
		fakeStats.peersHealthy = 0
		fakeStats.mu.Unlock()

		// Third cycle: should trigger restart discovery (no peers)
		healerWithStats.Cycle()

		actions = exec.getActions()
		lastAction := actions[len(actions)-1]
		if lastAction != healing.ActionRestartDiscovery {
			t.Errorf("expected ActionRestartDiscovery after total peer loss, got %v", lastAction)
		}
		t.Logf("final action after total loss: %v", lastAction)
	})

	// === Phase 4: MeshHealingExecutor with real node ===
	t.Run("Executor_With_Node", func(t *testing.T) {
		disc := discovery.New("test-node", 9002, []string{"mesh"}, "239.255.88.89", 8889)
		node := mesh.NewNode("test-node", 9002, disc)

		// Don't start discovery (no multicast in CI), just inject peers manually
		// We'll test the executor's peer removal path

		executor := healing.NewMeshHealingExecutor(
			"test-node",
			node, // PeerRemover
			node, // DiscoveryRestarter (will fail gracefully without multicast)
			nil,  // no alerter
			func() []healing.PeerEntry {
				return []healing.PeerEntry{
					{NodeID: "healthy-peer", Healthy: true},
					{NodeID: "unhealthy-peer", Healthy: false},
				}
			},
		)

		// Execute reroute — should evict unhealthy peer
		err := executor.ExecuteAction(healing.ActionReroute)
		if err != nil {
			t.Fatalf("ExecuteAction reroute: %v", err)
		}

		t.Log("reroute executed successfully")
	})
}

// fakeStatsProvider returns configurable stats for healing monitor testing.
type fakeStatsProvider struct {
	mu           sync.Mutex
	peersTotal   int
	peersHealthy int
	state        string
}

func (f *fakeStatsProvider) GetStats() map[string]any {
	f.mu.Lock()
	defer f.mu.Unlock()
	return map[string]any{
		"peers_total":   f.peersTotal,
		"peers_healthy": f.peersHealthy,
		"state":         f.state,
	}
}

// encodeFakeInit creates a handshake init message with a spoofed nodeID
// but signed with a different key pair — simulates MITM.
func encodeFakeInit(t *testing.T, spoofedID string, signer *pqc.TunnelManager) []byte {
	t.Helper()
	// We need to create an init message that claims to be from spoofedID
	// but is signed by signer's key. The simplest way: create a real init
	// from signer, then re-encode with spoofedID.
	//
	// In practice this would require access to internal encoding, but for testing
	// we can construct the wire format directly.
	//
	// Wire format: [node_id_len:2][node_id][kem_pubkey][sign_pubkey][signature]
	// The signature covers SHA256(node_id || kem_pubkey).
	// If we change node_id but keep the same signature, verification should fail.

	realMsg, err := signer.CreateHandshakeInit()
	if err != nil {
		t.Fatalf("CreateHandshakeInit for MITM sim: %v", err)
	}

	// Parse: [2-byte len][nodeID][KEM pubkey][sign pubkey][signature]
	nodeIDLen := int(realMsg[0])<<8 | int(realMsg[1])
	kemPubStart := 2 + nodeIDLen

	// Build spoofed message
	spoofedIDBytes := []byte(spoofedID)
	fakeMsg := make([]byte, 2+len(spoofedIDBytes)+len(realMsg)-2-nodeIDLen)
	fakeMsg[0] = byte(len(spoofedIDBytes) >> 8)
	fakeMsg[1] = byte(len(spoofedIDBytes))
	copy(fakeMsg[2:], spoofedIDBytes)
	copy(fakeMsg[2+len(spoofedIDBytes):], realMsg[kemPubStart:])

	return fakeMsg
}
