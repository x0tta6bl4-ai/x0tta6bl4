package mesh

import (
	"log/slog"
	"net"
	"testing"
	"time"
)

func newTestNode() *Node {
	return &Node{
		peers:    make(map[string]*Peer),
		resolver: NewConflictResolver(),
		State:    StateActive,
		logger:   slog.Default().With("component", "test"),
	}
}

func TestCheckPeerHealth_Healthy(t *testing.T) {
	n := newTestNode()

	// Add fresh peer
	n.peers["peer-1"] = &Peer{
		NodeID:   "peer-1",
		Addr:     &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000},
		LastSeen: time.Now(),
		Healthy:  true,
	}

	n.checkPeerHealth()

	if n.State != StateActive {
		t.Errorf("State = %v, want StateActive", n.State)
	}
	if !n.peers["peer-1"].Healthy {
		t.Error("peer should be healthy")
	}
}

func TestCheckPeerHealth_Unhealthy(t *testing.T) {
	n := newTestNode()

	// Add stale peer (not seen for 60s)
	n.peers["peer-1"] = &Peer{
		NodeID:   "peer-1",
		Addr:     &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000},
		LastSeen: time.Now().Add(-60 * time.Second),
		Healthy:  true,
	}

	n.checkPeerHealth()

	if n.State != StateDegraded {
		t.Errorf("State = %v, want StateDegraded", n.State)
	}
	if n.peers["peer-1"].Healthy {
		t.Error("peer should be unhealthy")
	}
}

func TestCheckPeerHealth_AutoRemove(t *testing.T) {
	n := newTestNode()

	// Add very stale peer (not seen for 3 minutes)
	n.peers["peer-stale"] = &Peer{
		NodeID:   "peer-stale",
		Addr:     &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000},
		LastSeen: time.Now().Add(-3 * time.Minute),
		Healthy:  false,
	}

	// Add fresh peer
	n.peers["peer-fresh"] = &Peer{
		NodeID:   "peer-fresh",
		Addr:     &net.UDPAddr{IP: net.IPv4(10, 0, 0, 2), Port: 5001},
		LastSeen: time.Now(),
		Healthy:  true,
	}

	n.checkPeerHealth()

	// Stale peer should be removed
	if _, exists := n.peers["peer-stale"]; exists {
		t.Error("stale peer should be removed")
	}

	// Fresh peer should remain
	if _, exists := n.peers["peer-fresh"]; !exists {
		t.Error("fresh peer should remain")
	}
}

func TestGetPeerHealthStats(t *testing.T) {
	n := newTestNode()

	n.peers["peer-1"] = &Peer{
		NodeID:    "peer-1",
		Addr:      &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000},
		LastSeen:  time.Now(),
		Healthy:   true,
		BytesSent: 1024,
		BytesRecv: 2048,
	}

	stats := n.GetPeerHealthStats()
	if len(stats) != 1 {
		t.Fatalf("stats length = %d, want 1", len(stats))
	}

	s := stats["peer-1"]
	if s.Status != "healthy" {
		t.Errorf("Status = %s, want healthy", s.Status)
	}
	if s.BytesSent != 1024 {
		t.Errorf("BytesSent = %d, want 1024", s.BytesSent)
	}
	if s.BytesRecv != 2048 {
		t.Errorf("BytesRecv = %d, want 2048", s.BytesRecv)
	}
}
