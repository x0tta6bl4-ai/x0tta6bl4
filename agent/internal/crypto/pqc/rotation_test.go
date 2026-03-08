package pqc

import (
	"context"
	"testing"
	"time"
)

func TestRotationManagerRotatesKEMAndPreservesOverlap(t *testing.T) {
	now := time.Date(2026, 3, 6, 12, 0, 0, 0, time.UTC)
	manager, err := NewRotationManager(context.Background(), RotationPolicy{
		Clock: func() time.Time { return now },
	}, nil, nil, nil)
	if err != nil {
		t.Fatalf("NewRotationManager: %v", err)
	}

	initial := manager.Snapshot(now)
	if len(initial.AcceptedKEM) != 1 {
		t.Fatalf("initial accepted KEM count = %d, want 1", len(initial.AcceptedKEM))
	}

	kemRotationTime := now.Add(DefaultKEMRotationInterval + time.Hour)
	events, err := manager.RotateDue(kemRotationTime)
	if err != nil {
		t.Fatalf("RotateDue(kem): %v", err)
	}
	if len(events) != 1 || events[0].KeyType != "kem" {
		t.Fatalf("unexpected kem rotation events: %+v", events)
	}

	postKEM := manager.Snapshot(kemRotationTime)
	if len(postKEM.AcceptedKEM) != 2 {
		t.Fatalf("accepted KEM count after rotation = %d, want 2", len(postKEM.AcceptedKEM))
	}
	if postKEM.ActiveKEM.KeyID == initial.ActiveKEM.KeyID {
		t.Fatal("expected a new active KEM key")
	}
	if !manager.AcceptsKEMPublicKey(initial.ActiveKEM.PublicKey, kemRotationTime) {
		t.Fatal("expected previous KEM key to remain accepted during overlap")
	}

	afterOverlap := kemRotationTime.Add(DefaultOverlapPeriod + time.Hour)
	if manager.AcceptsKEMPublicKey(initial.ActiveKEM.PublicKey, afterOverlap) {
		t.Fatal("expected previous KEM key to expire after overlap")
	}
}

func TestRotationManagerRotatesSignatureAndStoresNTRUBackup(t *testing.T) {
	now := time.Date(2026, 3, 6, 12, 0, 0, 0, time.UTC)
	manager, err := NewRotationManager(context.Background(), RotationPolicy{
		Clock: func() time.Time { return now },
	}, nil, nil, nil)
	if err != nil {
		t.Fatalf("NewRotationManager: %v", err)
	}

	initial := manager.Snapshot(now)
	if err := manager.RegisterNTRUBackup("pqc-backup-secret", []byte("ntru-pub"), []byte("ntru-priv")); err != nil {
		t.Fatalf("RegisterNTRUBackup: %v", err)
	}

	signRotationTime := now.Add(DefaultSignatureRotationInterval + time.Hour)
	events, err := manager.RotateDue(signRotationTime)
	if err != nil {
		t.Fatalf("RotateDue(signature): %v", err)
	}
	if len(events) == 0 {
		t.Fatal("expected at least one rotation event")
	}

	snapshot := manager.Snapshot(signRotationTime)
	if len(snapshot.BackupReferences) != 1 {
		t.Fatalf("backup reference count = %d, want 1", len(snapshot.BackupReferences))
	}
	if snapshot.BackupReferences[0].Algorithm != "NTRU-HRSS-701" {
		t.Fatalf("backup algorithm = %s, want NTRU-HRSS-701", snapshot.BackupReferences[0].Algorithm)
	}
	if !manager.AcceptsSignaturePublicKey(initial.ActiveSignature.PublicKey, signRotationTime) {
		t.Fatal("expected previous signature key to remain accepted during overlap")
	}
}
