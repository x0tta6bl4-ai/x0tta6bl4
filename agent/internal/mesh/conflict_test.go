package mesh

import (
	"net"
	"testing"
)

func TestConflictResolver_NewPeer(t *testing.T) {
	cr := NewConflictResolver()

	addr := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000}
	resolved, isUpdate, conflict := cr.ResolvePeer("peer-1", addr, "mdns")

	if isUpdate {
		t.Error("expected isUpdate=false for new peer")
	}
	if conflict != "" {
		t.Errorf("expected no conflict, got: %s", conflict)
	}
	if !resolved.IP.Equal(addr.IP) || resolved.Port != addr.Port {
		t.Errorf("resolved addr = %v, want %v", resolved, addr)
	}
}

func TestConflictResolver_DuplicateSameAddr(t *testing.T) {
	cr := NewConflictResolver()

	addr := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000}
	cr.ResolvePeer("peer-1", addr, "mdns")

	// Same address from different source — no conflict
	resolved, isUpdate, conflict := cr.ResolvePeer("peer-1", addr, "udp")

	if isUpdate {
		t.Error("expected isUpdate=false for same address")
	}
	if conflict != "" {
		t.Errorf("expected no conflict, got: %s", conflict)
	}
	_ = resolved
}

func TestConflictResolver_AddressChange(t *testing.T) {
	cr := NewConflictResolver()

	addr1 := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000}
	cr.ResolvePeer("peer-1", addr1, "mdns")

	// Address changed — conflict detected
	addr2 := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 2), Port: 5001}
	resolved, isUpdate, conflict := cr.ResolvePeer("peer-1", addr2, "udp")

	if !isUpdate {
		t.Error("expected isUpdate=true for address change")
	}
	if conflict == "" {
		t.Error("expected conflict info for address change")
	}
	if !resolved.IP.Equal(addr2.IP) {
		t.Errorf("resolved IP = %v, want %v", resolved.IP, addr2.IP)
	}
}

func TestConflictResolver_RemovePeer(t *testing.T) {
	cr := NewConflictResolver()

	addr := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000}
	cr.ResolvePeer("peer-1", addr, "mdns")

	cr.RemovePeer("peer-1")

	if cr.GetSource("peer-1") != "" {
		t.Error("expected empty source after remove")
	}
	if len(cr.GetHistory("peer-1")) != 0 {
		t.Error("expected empty history after remove")
	}
}

func TestConflictResolver_History(t *testing.T) {
	cr := NewConflictResolver()

	addr1 := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000}
	cr.ResolvePeer("peer-1", addr1, "mdns")

	addr2 := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 2), Port: 5001}
	cr.ResolvePeer("peer-1", addr2, "udp")

	history := cr.GetHistory("peer-1")
	if len(history) != 2 {
		t.Errorf("history length = %d, want 2", len(history))
	}
	if history[0].Source != "mdns" {
		t.Errorf("history[0].Source = %s, want mdns", history[0].Source)
	}
	if history[1].Source != "udp" {
		t.Errorf("history[1].Source = %s, want udp", history[1].Source)
	}
}

func TestConflictResolver_SourceTracking(t *testing.T) {
	cr := NewConflictResolver()

	addr := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 1), Port: 5000}
	cr.ResolvePeer("peer-1", addr, "mdns")

	if cr.GetSource("peer-1") != "mdns" {
		t.Errorf("source = %s, want mdns", cr.GetSource("peer-1"))
	}

	// Update source
	addr2 := &net.UDPAddr{IP: net.IPv4(10, 0, 0, 2), Port: 5001}
	cr.ResolvePeer("peer-1", addr2, "mDNS")

	if cr.GetSource("peer-1") != "mDNS" {
		t.Errorf("source = %s, want mDNS", cr.GetSource("peer-1"))
	}
}
