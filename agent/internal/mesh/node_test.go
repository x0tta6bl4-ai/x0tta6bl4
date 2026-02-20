package mesh

import (
	"net"
	"testing"
	"time"

	"github.com/x0tta6bl4/agent/internal/mesh/discovery"
)

func TestNewNode(t *testing.T) {
	n := NewNode("test-node", 5000, nil)
	if n.ID != "test-node" {
		t.Errorf("ID = %s, want test-node", n.ID)
	}
	if n.ListenPort != 5000 {
		t.Errorf("ListenPort = %d, want 5000", n.ListenPort)
	}
	if n.State != StateInit {
		t.Errorf("State = %v, want StateInit", n.State)
	}
	if n.peers == nil {
		t.Error("peers map should be initialized")
	}
}

func TestNodeState_String(t *testing.T) {
	cases := []struct {
		state NodeState
		want  string
	}{
		{StateInit, "init"},
		{StateConnecting, "connecting"},
		{StateActive, "active"},
		{StateDegraded, "degraded"},
		{StateStopped, "stopped"},
		{NodeState(99), "unknown"},
	}
	for _, c := range cases {
		if got := c.state.String(); got != c.want {
			t.Errorf("State(%d).String() = %s, want %s", c.state, got, c.want)
		}
	}
}

func TestGetStats_EmptyNode(t *testing.T) {
	n := NewNode("stats-node", 5001, nil)
	n.started = time.Now()

	stats := n.GetStats()

	if stats["node_id"] != "stats-node" {
		t.Errorf("node_id = %v", stats["node_id"])
	}
	if stats["peers_total"] != 0 {
		t.Errorf("peers_total = %v, want 0", stats["peers_total"])
	}
	if stats["peers_healthy"] != 0 {
		t.Errorf("peers_healthy = %v, want 0", stats["peers_healthy"])
	}
	if stats["health_score"] != 0.0 {
		t.Errorf("health_score = %v, want 0.0", stats["health_score"])
	}
	if stats["state"] != "init" {
		t.Errorf("state = %v, want init", stats["state"])
	}
}

func TestGetStats_WithPeers(t *testing.T) {
	n := NewNode("stats-node2", 5002, nil)
	n.started = time.Now()

	n.peers["peer-a"] = &Peer{NodeID: "peer-a", Healthy: true, LastSeen: time.Now()}
	n.peers["peer-b"] = &Peer{NodeID: "peer-b", Healthy: true, LastSeen: time.Now()}
	n.peers["peer-c"] = &Peer{NodeID: "peer-c", Healthy: false, LastSeen: time.Now()}

	stats := n.GetStats()

	if stats["peers_total"] != 3 {
		t.Errorf("peers_total = %v, want 3", stats["peers_total"])
	}
	if stats["peers_healthy"] != 2 {
		t.Errorf("peers_healthy = %v, want 2", stats["peers_healthy"])
	}
	score, ok := stats["health_score"].(float64)
	if !ok || score < 0.66 || score > 0.67 {
		t.Errorf("health_score = %v, want ~0.666", stats["health_score"])
	}
}

func TestGetPeers(t *testing.T) {
	n := NewNode("peer-node", 5003, nil)
	n.peers["x"] = &Peer{NodeID: "x", Healthy: true}
	n.peers["y"] = &Peer{NodeID: "y", Healthy: false}

	peers := n.GetPeers()
	if len(peers) != 2 {
		t.Errorf("GetPeers() len = %d, want 2", len(peers))
	}
}

func TestOnMessage_RegistersHandler(t *testing.T) {
	n := NewNode("msg-node", 5004, nil)
	n.OnMessage(func(data []byte, sender string, addr *net.UDPAddr) {})
	if len(n.handlers) != 1 {
		t.Errorf("handlers len = %d, want 1", len(n.handlers))
	}
}

func TestCheckPeerHealth_MarksUnhealthy(t *testing.T) {
	n := NewNode("health-node", 5005, nil)
	n.State = StateActive
	n.started = time.Now()

	n.peers["stale"] = &Peer{
		NodeID:   "stale",
		Healthy:  true,
		LastSeen: time.Now().Add(-60 * time.Second),
	}
	n.peers["fresh"] = &Peer{
		NodeID:   "fresh",
		Healthy:  true,
		LastSeen: time.Now(),
	}

	n.checkPeerHealth()

	if n.peers["stale"].Healthy {
		t.Error("stale peer should be marked unhealthy")
	}
	if !n.peers["fresh"].Healthy {
		t.Error("fresh peer should remain healthy")
	}
	if n.State != StateDegraded {
		t.Errorf("State = %v, want StateDegraded", n.State)
	}
}

func TestCheckPeerHealth_RecoveryToActive(t *testing.T) {
	n := NewNode("recover-node", 5006, nil)
	n.State = StateDegraded
	n.started = time.Now()

	n.peers["a"] = &Peer{NodeID: "a", Healthy: false, LastSeen: time.Now()}
	n.peers["b"] = &Peer{NodeID: "b", Healthy: false, LastSeen: time.Now()}

	n.checkPeerHealth()

	if n.State != StateActive {
		t.Errorf("State = %v, want StateActive after all peers fresh", n.State)
	}
}

func TestAddPeerFromDiscovery_Valid(t *testing.T) {
	n := NewNode("disc-node", 5007, nil)

	info := discovery.PeerInfo{
		NodeID:    "peer-xyz",
		Addresses: [][]any{{"192.168.1.10", float64(5000)}},
		Services:  []string{"mesh"},
	}
	n.addPeerFromDiscovery(info)

	n.mu.RLock()
	peer, ok := n.peers["peer-xyz"]
	n.mu.RUnlock()

	if !ok {
		t.Fatal("peer-xyz not added")
	}
	if peer.NodeID != "peer-xyz" {
		t.Errorf("NodeID = %s", peer.NodeID)
	}
	if peer.Addr.Port != 5000 {
		t.Errorf("Port = %d, want 5000", peer.Addr.Port)
	}
	if !peer.Healthy {
		t.Error("newly added peer should be healthy")
	}
}

func TestAddPeerFromDiscovery_NoAddress(t *testing.T) {
	n := NewNode("disc-node2", 5008, nil)
	info := discovery.PeerInfo{NodeID: "no-addr", Addresses: nil}
	n.addPeerFromDiscovery(info) // should not panic
	if _, ok := n.peers["no-addr"]; ok {
		t.Error("peer with no address should not be added")
	}
}

func TestAddPeerFromDiscovery_ShortAddress(t *testing.T) {
	n := NewNode("disc-node3", 5008, nil)
	info := discovery.PeerInfo{NodeID: "short", Addresses: [][]any{{"only-ip"}}}
	n.addPeerFromDiscovery(info) // address too short, port==0
	if _, ok := n.peers["short"]; ok {
		t.Error("peer with single-element address should not be added")
	}
}

func TestRemovePeer(t *testing.T) {
	n := NewNode("remove-node", 5009, nil)
	n.peers["to-remove"] = &Peer{NodeID: "to-remove"}
	n.removePeer("to-remove")
	if _, ok := n.peers["to-remove"]; ok {
		t.Error("peer should be removed")
	}
}

func TestGetStats_UptimeSec(t *testing.T) {
	n := NewNode("uptime-node", 5010, nil)
	n.started = time.Now().Add(-5 * time.Second)

	stats := n.GetStats()
	uptime, ok := stats["uptime_sec"].(float64)
	if !ok || uptime < 4.0 {
		t.Errorf("uptime_sec = %v, want >= 4.0", stats["uptime_sec"])
	}
}
