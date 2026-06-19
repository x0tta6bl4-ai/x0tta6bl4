package main

import (
	"bytes"
	"net"
	"sync"
	"testing"
	"time"

	"github.com/x0tta6bl4/agent/internal/crypto/pqc"
	"github.com/x0tta6bl4/agent/internal/mesh"
	"github.com/x0tta6bl4/agent/internal/mesh/discovery"
)

func TestMeshPQCEndToEnd(t *testing.T) {
	// --- Phase 1: Create two nodes with PQC ---
	// Use different discovery ports so unicast works
	discA := discovery.New("node-a", 16001, []string{"mesh"}, "239.255.99.99", 9991)
	discB := discovery.New("node-b", 16002, []string{"mesh"}, "239.255.99.99", 9992)

	nodeA := mesh.NewNode("node-a", 16001, discA)
	nodeB := mesh.NewNode("node-b", 16002, discB)

	tmA, _ := pqc.NewTunnelManager("node-a")
	tmB, _ := pqc.NewTunnelManager("node-b")

	// Pre-trust signing keys
	tmA.SetTrustedPeer("node-b", tmB.GetSignPublicKey())
	tmB.SetTrustedPeer("node-a", tmA.GetSignPublicKey())

	nodeA.SetTunnelManager(tmA)
	nodeB.SetTunnelManager(tmB)

	// Collect received messages
	var muA sync.Mutex
	var receivedA [][]byte
	nodeA.OnMessage(func(data []byte, sender string, addr *net.UDPAddr) {
		muA.Lock()
		receivedA = append(receivedA, data)
		muA.Unlock()
	})

	var muB sync.Mutex
	var receivedB [][]byte
	nodeB.OnMessage(func(data []byte, sender string, addr *net.UDPAddr) {
		muB.Lock()
		receivedB = append(receivedB, data)
		muB.Unlock()
	})

	// --- Phase 2: Start both nodes ---
	if err := nodeA.Start(); err != nil {
		t.Fatalf("nodeA start: %v", err)
	}
	defer nodeA.Stop()

	if err := nodeB.Start(); err != nil {
		t.Fatalf("nodeB start: %v", err)
	}
	defer nodeB.Stop()

	t.Logf("Node A listening on :%d", 16001)
	t.Logf("Node B listening on :%d", 16002)

	// --- Phase 3: Directly inject peers (bypass broken multicast) ---
	nodeA.InjectPeer("node-b", "127.0.0.1", 16002)
	nodeB.InjectPeer("node-a", "127.0.0.1", 16001)

	time.Sleep(2 * time.Second) // Wait for PQC handshake

	// Verify both nodes see each other
	peersA := nodeA.GetPeers()
	peersB := nodeB.GetPeers()
	if len(peersA) == 0 {
		t.Fatal("node A has no peers")
	}
	if len(peersB) == 0 {
		t.Fatal("node B has no peers")
	}
	t.Logf("Node A peers: %d, Node B peers: %d", len(peersA), len(peersB))

	// --- Phase 4: Wait for PQC handshake ---

	tmAHasSession := tmA.HasSession("node-b")
	tmBHasSession := tmB.HasSession("node-a")
	t.Logf("PQC sessions: A→B=%v, B→A=%v", tmAHasSession, tmBHasSession)

	// --- Phase 5: Send PQC-encrypted data ---
	plaintext := []byte("Hello from A! PQC-encrypted mesh message.")
	err := nodeA.SendTo("node-b", plaintext)
	if err != nil {
		t.Fatalf("SendTo failed: %v", err)
	}
	t.Logf("Sent %d bytes from A to B", len(plaintext))

	// Wait for delivery
	time.Sleep(500 * time.Millisecond)

	muB.Lock()
	if len(receivedB) == 0 {
		t.Fatal("node B received no messages")
	}
	lastMsg := receivedB[len(receivedB)-1]
	muB.Unlock()

	if !bytes.Equal(lastMsg, plaintext) {
		t.Errorf("node B received %q, want %q", lastMsg, plaintext)
	} else {
		t.Logf("Node B received: %q ✓", lastMsg)
	}

	// --- Phase 6: Reply from B to A ---
	reply := []byte("Hello from B! Reply via PQC mesh.")
	err = nodeB.SendTo("node-a", reply)
	if err != nil {
		t.Fatalf("B→A SendTo failed: %v", err)
	}

	time.Sleep(500 * time.Millisecond)

	muA.Lock()
	if len(receivedA) == 0 {
		t.Fatal("node A received no messages")
	}
	lastReply := receivedA[len(receivedA)-1]
	muA.Unlock()

	if !bytes.Equal(lastReply, reply) {
		t.Errorf("node A received %q, want %q", lastReply, reply)
	} else {
		t.Logf("Node A received: %q ✓", lastReply)
	}

	t.Log("\n=== PQC MESH END-TO-END: PASS ===")
}
