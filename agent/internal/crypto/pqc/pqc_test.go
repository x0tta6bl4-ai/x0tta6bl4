package pqc

import (
	"bytes"
	"encoding/binary"
	"testing"

	"github.com/cloudflare/circl/kem/mlkem/mlkem768"
	"github.com/cloudflare/circl/sign/mldsa/mldsa65"
)

func TestNewTunnelManager(t *testing.T) {
	tm, err := NewTunnelManager("node-a")
	if err != nil {
		t.Fatalf("NewTunnelManager: %v", err)
	}
	if tm.nodeID != "node-a" {
		t.Errorf("nodeID = %s, want node-a", tm.nodeID)
	}
	if len(tm.GetPublicKey()) != mlkem768.PublicKeySize {
		t.Errorf("KEM public key length = %d, want %d", len(tm.GetPublicKey()), mlkem768.PublicKeySize)
	}
	if len(tm.GetSignPublicKey()) != mldsa65.PublicKeySize {
		t.Errorf("Sign public key length = %d, want %d", len(tm.GetSignPublicKey()), mldsa65.PublicKeySize)
	}
	if tm.keys.Algorithm != "ML-KEM-768" {
		t.Errorf("KEM algorithm = %s, want ML-KEM-768", tm.keys.Algorithm)
	}
	if tm.signKeys.Algorithm != "ML-DSA-65" {
		t.Errorf("Sign algorithm = %s, want ML-DSA-65", tm.signKeys.Algorithm)
	}
}

func TestHandshakeRoundTrip(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")

	// Pre-trust each other's signing keys (in production this comes from control plane)
	bob.SetTrustedPeer("alice", alice.GetSignPublicKey())
	alice.SetTrustedPeer("bob", bob.GetSignPublicKey())

	// 1. Alice initiates handshake
	initMsg, err := alice.CreateHandshakeInit()
	if err != nil {
		t.Fatalf("Alice CreateHandshakeInit: %v", err)
	}

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

func TestHandshakeTOFU(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")

	// No pre-trust — TOFU mode should still work
	initMsg, err := alice.CreateHandshakeInit()
	if err != nil {
		t.Fatalf("CreateHandshakeInit: %v", err)
	}

	peerID_B, _, respMsg, err := bob.ProcessHandshakeInit(initMsg)
	if err != nil {
		t.Fatalf("ProcessHandshakeInit: %v", err)
	}
	if peerID_B != "alice" {
		t.Errorf("peerID = %s, want alice", peerID_B)
	}

	peerID_A, _, err := alice.ProcessHandshakeResponse(respMsg)
	if err != nil {
		t.Fatalf("ProcessHandshakeResponse: %v", err)
	}
	if peerID_A != "bob" {
		t.Errorf("peerID = %s, want bob", peerID_A)
	}
}

func TestHandshakeMITMDetected(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")
	mallory, _ := NewTunnelManager("mallory")

	// Alice trusts bob's REAL signing key
	alice.SetTrustedPeer("bob", bob.GetSignPublicKey())

	// Mallory tries to impersonate bob — signs with her own key
	initMsg, err := mallory.CreateHandshakeInit()
	if err != nil {
		t.Fatalf("CreateHandshakeInit: %v", err)
	}

	// Alice receives init claiming to be from "bob" but signed by mallory
	// We simulate: mallory's init is sent to alice (not bob)
	// Alice processes it — signature verification should fail
	_, _, _, err = alice.ProcessHandshakeInit(initMsg)
	// This should succeed (it's a valid init from mallory's perspective)
	// but the peerID will be "mallory", not "bob"
	if err != nil {
		t.Fatalf("ProcessHandshakeInit: %v", err)
	}

	// Now test: bob sends response, but alice expects bob's signing key
	// If mallory intercepts and re-signs, alice should reject
	// Simulate: mallory creates a response with her signing key
	initMsg2, _ := bob.CreateHandshakeInit()
	_, _, _, _ = mallory.ProcessHandshakeInit(initMsg2)

	// Alice tries to process mallory's response (claiming to be "mallory")
	// but alice trusts bob's key, not mallory's
	// This is fine — alice doesn't trust "mallory"

	// The real MITM test: mallory intercepts bob's init, replaces signing key
	// We simulate by modifying bob's init message
	bobInit, _ := bob.CreateHandshakeInit()
	// Parse: [node_id_len:2][node_id][kem_pubkey][sign_pubkey][signature]
	nodeIDLen := int(binary.BigEndian.Uint16(bobInit[0:2]))
	fakeInit := make([]byte, len(bobInit))
	copy(fakeInit, bobInit)
	// Replace sign_pubkey with mallory's
	mallorySignOffset := 2 + nodeIDLen + mlkem768.PublicKeySize
	copy(fakeInit[mallorySignOffset:], mallory.GetSignPublicKey())

	// Alice receives the tampered init — should reject because signing key doesn't match bob's trusted key
	_, _, _, err = alice.ProcessHandshakeInit(fakeInit)
	if err == nil {
		t.Error("expected MITM detection error, got nil")
	}
}

func TestEncryptDecrypt_Session(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")

	init, _ := alice.CreateHandshakeInit()
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
	init, _ := alice.CreateHandshakeInit()
	_, _, resp, _ := bob.ProcessHandshakeInit(init)
	alice.ProcessHandshakeResponse(resp)

	data := []byte("framed data")
	wrapped, err := alice.WrapPacket(data, "bob")
	if err != nil {
		t.Fatalf("WrapPacket: %v", err)
	}

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

	// Invalid KEM PK
	badPK := make([]byte, 2+4+mldsa65.PublicKeySize+mldsa65.SignatureSize)
	binary.BigEndian.PutUint16(badPK[0:2], 4)
	copy(badPK[2:], "peer")
	// Leave KEM key as zeros — invalid
	_, _, _, err = tm.ProcessHandshakeInit(badPK)
	if err == nil {
		t.Error("expected error for invalid KEM PK")
	}
}

func TestRemoveSession(t *testing.T) {
	alice, _ := NewTunnelManager("alice")
	bob, _ := NewTunnelManager("bob")
	init, _ := alice.CreateHandshakeInit()
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
		t.Error("KEM keys should differ between nodes")
	}
	if bytes.Equal(tm1.GetSignPublicKey(), tm2.GetSignPublicKey()) {
		t.Error("Signing keys should differ between nodes")
	}
}

func TestTrustedPeerManagement(t *testing.T) {
	tm, _ := NewTunnelManager("node")

	tm.SetTrustedPeer("peer-1", []byte("key-1"))
	tm.SetTrustedPeer("peer-2", []byte("key-2"))

	tm.mu.RLock()
	if len(tm.trustedPeers) != 2 {
		t.Errorf("trusted peers = %d, want 2", len(tm.trustedPeers))
	}
	tm.mu.RUnlock()

	tm.RemoveTrustedPeer("peer-1")
	tm.mu.RLock()
	if len(tm.trustedPeers) != 1 {
		t.Errorf("trusted peers after remove = %d, want 1", len(tm.trustedPeers))
	}
	tm.mu.RUnlock()
}

func TestSignTranscriptConsistency(t *testing.T) {
	tm, _ := NewTunnelManager("node")
	transcript := []byte("test-transcript-data")

	sig1, err := tm.signTranscript(transcript)
	if err != nil {
		t.Fatalf("signTranscript: %v", err)
	}
	sig2, err := tm.signTranscript(transcript)
	if err != nil {
		t.Fatalf("signTranscript: %v", err)
	}

	if !bytes.Equal(sig1, sig2) {
		t.Error("ML-DSA signatures should be deterministic for same input")
	}

	// Verify
	ok, err := verifyTranscript(tm.signKeys.PublicKey, transcript, sig1)
	if err != nil {
		t.Fatalf("verifyTranscript: %v", err)
	}
	if !ok {
		t.Error("signature verification should succeed")
	}
}
