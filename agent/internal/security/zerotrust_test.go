package security

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestPolicyEngineReverificationAndLeastPrivilege(t *testing.T) {
	now := time.Date(2026, 3, 6, 12, 0, 0, 0, time.UTC)
	auditDir := t.TempDir()
	trail, err := NewTamperEvidentAuditTrail(AuditTrailConfig{
		Directory: auditDir,
		Clock:     func() time.Time { return now },
	})
	if err != nil {
		t.Fatalf("NewTamperEvidentAuditTrail: %v", err)
	}

	filters := NewMemoryFilterManager()
	engine, err := NewPolicyEngine(PolicyEngineConfig{
		Clock:            func() time.Time { return now },
		ReverifyInterval: 10 * time.Minute,
		Filters:          filters,
		AuditTrail:       trail,
	})
	if err != nil {
		t.Fatalf("NewPolicyEngine: %v", err)
	}

	err = engine.UpsertPeerPolicy(nil, PeerPolicy{
		PeerID:            "peer-a",
		AllowedSignatures: []string{"sigfp"},
		AllowedKEMKeys:    []string{"kemfp"},
		Permissions: []Permission{
			PermissionTopologyRead,
			PermissionTopologyWrite,
		},
		AllowedCIDRs: []string{"10.0.0.0/24"},
		AllowedPorts: []uint16{7000, 7443},
	})
	if err != nil {
		t.Fatalf("UpsertPeerPolicy: %v", err)
	}

	rules := filters.RulesForPeer("peer-a")
	if len(rules) != 2 {
		t.Fatalf("rule count = %d, want 2", len(rules))
	}

	decision, err := engine.AuthorizeAction("peer-a", PermissionTopologyRead)
	if err != nil {
		t.Fatalf("AuthorizeAction(before handshake): %v", err)
	}
	if decision.Allowed {
		t.Fatal("expected action to be denied before initial authentication")
	}
	if !decision.ReverifyRequired {
		t.Fatal("expected re-verification requirement")
	}

	decision, err = engine.AuthorizeHandshake("peer-a", "sigfp", "kemfp")
	if err != nil {
		t.Fatalf("AuthorizeHandshake: %v", err)
	}
	if !decision.Allowed {
		t.Fatal("expected handshake to be allowed")
	}

	decision, err = engine.AuthorizeAction("peer-a", PermissionTopologyWrite)
	if err != nil {
		t.Fatalf("AuthorizeAction(write): %v", err)
	}
	if !decision.Allowed {
		t.Fatal("expected topology.write to be allowed")
	}

	decision, err = engine.AuthorizeAction("peer-a", PermissionRelay)
	if err != nil {
		t.Fatalf("AuthorizeAction(relay): %v", err)
	}
	if decision.Allowed {
		t.Fatal("expected mesh.relay to be denied by least privilege")
	}

	now = now.Add(11 * time.Minute)
	decision, err = engine.AuthorizeAction("peer-a", PermissionTopologyRead)
	if err != nil {
		t.Fatalf("AuthorizeAction(after interval): %v", err)
	}
	if decision.Allowed {
		t.Fatal("expected action to be denied after reverify window elapsed")
	}
	if !decision.ReverifyRequired {
		t.Fatal("expected reverify requirement after interval elapsed")
	}
}

func TestAuditTrailHashChainAndRetention(t *testing.T) {
	now := time.Date(2026, 3, 6, 12, 0, 0, 0, time.UTC)
	trail, err := NewTamperEvidentAuditTrail(AuditTrailConfig{
		Directory: t.TempDir(),
		Clock:     func() time.Time { return now },
		Retention: 365 * 24 * time.Hour,
	})
	if err != nil {
		t.Fatalf("NewTamperEvidentAuditTrail: %v", err)
	}

	first, err := trail.Append("handshake", "peer-a", "allow", map[string]any{"mode": "hybrid"})
	if err != nil {
		t.Fatalf("Append(first): %v", err)
	}
	if first.PreviousHash != "" {
		t.Fatalf("first previous hash = %q, want empty", first.PreviousHash)
	}

	now = now.Add(2 * time.Hour)
	second, err := trail.Append("policy.decision", "peer-a", "allow", map[string]any{"permission": "topology.read"})
	if err != nil {
		t.Fatalf("Append(second): %v", err)
	}
	if second.PreviousHash != first.EntryHash {
		t.Fatal("expected second entry to chain to first entry")
	}

	now = now.Add(366 * 24 * time.Hour)
	if _, err := trail.Append("handshake", "peer-b", "deny", map[string]any{"reason": "expired"}); err != nil {
		t.Fatalf("Append(third): %v", err)
	}

	files, err := filepath.Glob(filepath.Join(trail.cfg.Directory, "audit-*.jsonl"))
	if err != nil {
		t.Fatalf("Glob(audit files): %v", err)
	}
	if len(files) != 1 {
		t.Fatalf("audit file count after retention = %d, want 1", len(files))
	}

	content, err := os.ReadFile(files[0])
	if err != nil {
		t.Fatalf("ReadFile(audit): %v", err)
	}
	lines := strings.Split(strings.TrimSpace(string(content)), "\n")
	if len(lines) != 1 {
		t.Fatalf("expected only retained day's record, got %d lines", len(lines))
	}

	var record AuditEvent
	if err := json.Unmarshal([]byte(lines[0]), &record); err != nil {
		t.Fatalf("json.Unmarshal(audit line): %v", err)
	}
	if record.EntryHash == "" {
		t.Fatal("expected entry hash in retained audit record")
	}
}
