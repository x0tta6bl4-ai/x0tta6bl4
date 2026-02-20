package pqc

import (
	"bytes"
	"encoding/binary"
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
	// ML-KEM-768 public key size is 1184 bytes
	if len(tm.GetPublicKey()) != 1184 {
		t.Errorf("public key length = %d, want 1184", len(tm.GetPublicKey()))
	}
	if tm.keys.Algorithm != "ML-KEM-768" {
		t.Errorf("algorithm = %s, want ML-KEM-768", tm.keys.Algorithm)
	}
}

func TestHandshakeRoundTrip(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")

	// 1. Alice initiates handshake
	initMsg := alice.CreateHandshakeInit()

	// 2. Bob processes init and sends response
	peerID_B, ss_B, respMsg, err := bob.ProcessHandshakeInit(initMsg)
	if err != nil {
		t.Fatalf("Bob failed to process init: %v", err)
	}
	if peerID_B != "alice" {
		t.Errorf("Bob got peerID = %s, want alice", peerID_B)
	}

	// 3. Alice processes response
	peerID_A, ss_A, err := alice.ProcessHandshakeResponse(respMsg)
	if err != nil {
		t.Fatalf("Alice failed to process response: %v", err)
	}
	if peerID_A != "bob" {
		t.Errorf("Alice got peerID = %s, want bob", peerID_A)
	}

	// 4. Shared secrets must match
	if !bytes.Equal(ss_A, ss_B) {
		t.Error("shared secrets do not match")
	}

	if !alice.HasSession("bob") {
		t.Error("alice should have session with bob")
	}
	if !bob.HasSession("alice") {
		t.Error("bob should have session with alice")
	}
}

func TestEncryptDecrypt_Session(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")

	init := alice.CreateHandshakeInit()
	_, _, resp, _ := bob.ProcessHandshakeInit(init)
	alice.ProcessHandshakeResponse(resp)

	plaintext := []byte("hello quantum world")
	ciphertext, err := alice.Encrypt(plaintext, "bob")
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}

	decrypted, err := bob.Decrypt(ciphertext, "alice")
	if err != nil {
		t.Fatalf("Decrypt: %v", err)
	}
	if !bytes.Equal(plaintext, decrypted) {
		t.Errorf("decrypted = %q, want %q", decrypted, plaintext)
	}
}

func TestWrapUnwrap(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")
	init := alice.CreateHandshakeInit()
	_, _, resp, _ := bob.ProcessHandshakeInit(init)
	alice.ProcessHandshakeResponse(resp)

	data := []byte("framed data")
	wrapped, err := alice.WrapPacket(data, "bob")
	if err != nil {
		t.Fatalf("WrapPacket: %v", err)
	}

	// Check magic
	if string(wrapped[0:4]) != "PQC1" {
		t.Errorf("magic = %s, want PQC1", wrapped[0:4])
	}

	unwrapped, err := bob.UnwrapPacket(wrapped, "alice")
	if err != nil {
		t.Fatalf("UnwrapPacket: %v", err)
	}
	if !bytes.Equal(data, unwrapped) {
		t.Errorf("unwrapped = %q, want %q", unwrapped, data)
	}
}

func TestDeriveKeyConsistency(t *testing.T) {
	tm, _ := NewTunnelManager("test")
	ss := []byte("shared-secret-that-is-at-least-32-bytes-long")
	
	key1, _ := tm.deriveKey(ss)
	key2, _ := tm.deriveKey(ss)

	if !bytes.Equal(key1, key2) {
		t.Error("derived keys should be consistent")
	}
	if len(key1) != 32 {
		t.Errorf("key length = %d, want 32", len(key1))
	}
}

func TestHandshakeErrors(t *testing.T) {
	tm, _ := NewTunnelManager("node")

	// Truncated message
	_, _, _, err := tm.ProcessHandshakeInit([]byte{0, 5, 'a'})
	if err == nil {
		t.Error("expected error for truncated init")
	}

	// Invalid PK
	badPK := make([]byte, 2+4)
	binary.BigEndian.PutUint16(badPK[0:2], 4)
	copy(badPK[2:], "peer")
	copy(badPK[6:], []byte("not-a-pk"))
	_, _, _, err = tm.ProcessHandshakeInit(badPK)
	if err == nil {
		t.Error("expected error for invalid PK")
	}
}

func TestRemoveSession(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")
	init := alice.CreateHandshakeInit()
	_, _, resp, _ := bob.ProcessHandshakeInit(init)
	alice.ProcessHandshakeResponse(resp)

	if !alice.HasSession("bob") {
		t.Fatal("session should exist")
	}
	alice.RemoveSession("bob")
	if alice.HasSession("bob") {
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
