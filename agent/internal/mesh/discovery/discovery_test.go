package discovery

import (
	"encoding/json"
	"testing"
	"time"
)

func TestNew_Defaults(t *testing.T) {
	d := New("node-1", 5000, nil, "", 0)
	if d.nodeID != "node-1" {
		t.Errorf("nodeID = %s", d.nodeID)
	}
	if d.mcastGroup != DefaultMulticastGroup {
		t.Errorf("mcastGroup = %s, want %s", d.mcastGroup, DefaultMulticastGroup)
	}
	if d.mcastPort != DefaultMulticastPort {
		t.Errorf("mcastPort = %d, want %d", d.mcastPort, DefaultMulticastPort)
	}
	if len(d.services) != 1 || d.services[0] != "mesh" {
		t.Errorf("services = %v, want [mesh]", d.services)
	}
}

func TestNew_CustomValues(t *testing.T) {
	d := New("node-2", 6000, []string{"vpn", "mesh"}, "239.1.1.1", 8888)
	if d.mcastGroup != "239.1.1.1" {
		t.Errorf("mcastGroup = %s", d.mcastGroup)
	}
	if d.mcastPort != 8888 {
		t.Errorf("mcastPort = %d", d.mcastPort)
	}
	if len(d.services) != 2 {
		t.Errorf("services len = %d, want 2", len(d.services))
	}
}

func TestPeerCount_Empty(t *testing.T) {
	d := New("node-3", 5000, nil, "", 0)
	if d.PeerCount() != 0 {
		t.Errorf("PeerCount = %d, want 0", d.PeerCount())
	}
}

func TestGetPeers_Empty(t *testing.T) {
	d := New("node-4", 5000, nil, "", 0)
	peers := d.GetPeers()
	if len(peers) != 0 {
		t.Errorf("GetPeers len = %d, want 0", len(peers))
	}
}

func TestGetPeer_NotFound(t *testing.T) {
	d := New("node-5", 5000, nil, "", 0)
	if p := d.GetPeer("nonexistent"); p != nil {
		t.Error("GetPeer should return nil for unknown node")
	}
}

func TestGetPeer_Found(t *testing.T) {
	d := New("node-6", 5000, nil, "", 0)
	d.peers["test-peer"] = &PeerInfo{
		NodeID:   "test-peer",
		LastSeen: time.Now(),
	}
	p := d.GetPeer("test-peer")
	if p == nil {
		t.Fatal("GetPeer returned nil")
	}
	if p.NodeID != "test-peer" {
		t.Errorf("NodeID = %s", p.NodeID)
	}
}

func TestGetPeer_ReturnsCopy(t *testing.T) {
	d := New("node-7", 5000, nil, "", 0)
	original := &PeerInfo{NodeID: "test", LastSeen: time.Now()}
	d.peers["test"] = original

	got := d.GetPeer("test")
	got.NodeID = "modified"

	if d.peers["test"].NodeID != "test" {
		t.Error("GetPeer should return a copy, not pointer to internal state")
	}
}

func TestHandleMessage_IgnoresSelf(t *testing.T) {
	d := New("self-node", 5000, nil, "", 0)

	peer := PeerInfo{NodeID: "self-node", Addresses: [][]any{{"127.0.0.1", float64(5000)}}}
	payload, _ := json.Marshal(AnnouncePayload{Peer: peer})
	msg := Message{
		Type:    MsgAnnounce,
		Sender:  "self-node",
		Payload: payload,
		TS:      time.Now().UnixMilli(),
	}
	data, _ := json.Marshal(msg)
	d.handleMessage(data, nil)

	if d.PeerCount() != 0 {
		t.Error("should ignore own announcements")
	}
}

func TestHandleMessage_InvalidJSON(t *testing.T) {
	d := New("node-8", 5000, nil, "", 0)
	d.handleMessage([]byte("not json"), nil) // should not panic
}

func TestHandleLeave_RemovesPeer(t *testing.T) {
	d := New("node-9", 5000, nil, "", 0)

	lost := false
	d.OnPeerLost = func(p PeerInfo) { lost = true }

	d.peers["leaver"] = &PeerInfo{NodeID: "leaver", LastSeen: time.Now()}

	payload, _ := json.Marshal(struct{}{})
	msg := Message{
		Type:    MsgLeave,
		Sender:  "leaver",
		Payload: payload,
		TS:      time.Now().UnixMilli(),
	}
	data, _ := json.Marshal(msg)
	d.handleMessage(data, nil)

	if d.PeerCount() != 0 {
		t.Error("peer should be removed after leave")
	}
	if !lost {
		t.Error("OnPeerLost callback should be called")
	}
}

func TestHandleLeave_UnknownPeer(t *testing.T) {
	d := New("node-10", 5000, nil, "", 0)
	payload, _ := json.Marshal(struct{}{})
	msg := Message{Type: MsgLeave, Sender: "ghost", Payload: payload}
	data, _ := json.Marshal(msg)
	d.handleMessage(data, nil) // should not panic
}

func TestCleanupExpired(t *testing.T) {
	d := New("node-11", 5000, nil, "", 0)

	removedIDs := []string{}
	d.OnPeerLost = func(p PeerInfo) { removedIDs = append(removedIDs, p.NodeID) }

	d.peers["stale"] = &PeerInfo{NodeID: "stale", LastSeen: time.Now().Add(-2 * PeerTimeout)}
	d.peers["fresh"] = &PeerInfo{NodeID: "fresh", LastSeen: time.Now()}

	d.cleanupExpired()

	if d.PeerCount() != 1 {
		t.Errorf("PeerCount = %d, want 1 after cleanup", d.PeerCount())
	}
	if d.GetPeer("stale") != nil {
		t.Error("stale peer should be removed")
	}
	if d.GetPeer("fresh") == nil {
		t.Error("fresh peer should remain")
	}
	if len(removedIDs) != 1 || removedIDs[0] != "stale" {
		t.Errorf("OnPeerLost called with %v, want [stale]", removedIDs)
	}
}

func TestConstants(t *testing.T) {
	if DefaultMulticastGroup == "" {
		t.Error("DefaultMulticastGroup should not be empty")
	}
	if DefaultMulticastPort == 0 {
		t.Error("DefaultMulticastPort should not be 0")
	}
	if AnnounceInterval <= 0 {
		t.Error("AnnounceInterval should be positive")
	}
	if PeerTimeout <= 0 {
		t.Error("PeerTimeout should be positive")
	}
}

func TestMessageTypes(t *testing.T) {
	if MsgAnnounce != 0x01 {
		t.Errorf("MsgAnnounce = %d, want 1", MsgAnnounce)
	}
	if MsgLeave != 0x07 {
		t.Errorf("MsgLeave = %d, want 7", MsgLeave)
	}
}
