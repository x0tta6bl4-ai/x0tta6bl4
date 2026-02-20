package pqc

import (
	"bytes"
	"testing"
)

func TestNewTunnelManager(t *testing.T) {
	tm, err := NewTunnelManager("node-a")
	if err != nil {
		t.Fatalf("NewTunnelManager: %v", err)
	}
	if tm.nodeID != "node-a" {
		t.Errorf("nodeID = %s, want node-a", tm.nodeID)
	}
	if len(tm.GetPublicKey()) != 32 {
		t.Errorf("public key length = %d, want 32", len(tm.GetPublicKey()))
	}
	if tm.keys.Algorithm != "AES-256-GCM-FALLBACK" {
		t.Errorf("algorithm = %s, want AES-256-GCM-FALLBACK", tm.keys.Algorithm)
	}
}

func TestEstablishSession(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")

	// Exchange public keys and establish sessions
	if err := alice.EstablishSession("bob", bob.GetPublicKey()); err != nil {
		t.Fatalf("alice.EstablishSession: %v", err)
	}
	if err := bob.EstablishSession("alice", alice.GetPublicKey()); err != nil {
		t.Fatalf("bob.EstablishSession: %v", err)
	}

	if !alice.HasSession("bob") {
		t.Error("alice should have session with bob")
	}
	if !bob.HasSession("alice") {
		t.Error("bob should have session with alice")
	}
}

func TestEncryptDecrypt_SameKeys(t *testing.T) {
	// Two tunnel managers sharing the same derived key
	tm, _ := NewTunnelManager("sender")

	// Self-session (same key both sides)
	tm.EstablishSession("self", tm.GetPublicKey())

	plaintext := []byte("hello post-quantum world")
	ciphertext, err := tm.Encrypt(plaintext, "self")
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}

	if bytes.Equal(plaintext, ciphertext) {
		t.Error("ciphertext should differ from plaintext")
	}
	if len(ciphertext) <= len(plaintext) {
		t.Error("ciphertext should be longer (nonce + tag)")
	}

	decrypted, err := tm.Decrypt(ciphertext, "self")
	if err != nil {
		t.Fatalf("Decrypt: %v", err)
	}
	if !bytes.Equal(plaintext, decrypted) {
		t.Errorf("decrypted = %q, want %q", decrypted, plaintext)
	}
}

func TestEncrypt_NoSession(t *testing.T) {
	tm, _ := NewTunnelManager("node")
	_, err := tm.Encrypt([]byte("data"), "unknown-peer")
	if err == nil {
		t.Error("expected error for missing session")
	}
}

func TestDecrypt_NoSession(t *testing.T) {
	tm, _ := NewTunnelManager("node")
	_, err := tm.Decrypt([]byte("data"), "unknown-peer")
	if err == nil {
		t.Error("expected error for missing session")
	}
}

func TestDecrypt_TooShort(t *testing.T) {
	tm, _ := NewTunnelManager("node")
	tm.EstablishSession("peer", tm.GetPublicKey())
	_, err := tm.Decrypt([]byte("x"), "peer")
	if err == nil {
		t.Error("expected error for too-short ciphertext")
	}
}

func TestRemoveSession(t *testing.T) {
	tm, _ := NewTunnelManager("node")
	tm.EstablishSession("peer", tm.GetPublicKey())
	if !tm.HasSession("peer") {
		t.Fatal("session should exist")
	}
	tm.RemoveSession("peer")
	if tm.HasSession("peer") {
		t.Error("session should be removed")
	}
}

func TestKeyPairUniqueness(t *testing.T) {
	tm1, _ := NewTunnelManager("a")
	tm2, _ := NewTunnelManager("b")
	if bytes.Equal(tm1.GetPublicKey(), tm2.GetPublicKey()) {
		t.Error("different nodes should have different keys")
	}
}
