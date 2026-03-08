package pqc

import (
	"bytes"
	"context"
	"testing"
	"time"
)

func TestHybridNoiseRoundTrip(t *testing.T) {
	alice, err := NewHybridNoiseTransport(HybridNoiseConfig{
		NodeID:                 "alice",
		AllowClassicalFallback: true,
	})
	if err != nil {
		t.Fatalf("NewHybridNoiseTransport(alice): %v", err)
	}
	bob, err := NewHybridNoiseTransport(HybridNoiseConfig{
		NodeID:                 "bob",
		AllowClassicalFallback: true,
	})
	if err != nil {
		t.Fatalf("NewHybridNoiseTransport(bob): %v", err)
	}

	initState, initMsg, err := alice.StartInitiatorHandshake()
	if err != nil {
		t.Fatalf("StartInitiatorHandshake: %v", err)
	}

	wireInit, err := initMsg.MarshalBinary()
	if err != nil {
		t.Fatalf("init MarshalBinary: %v", err)
	}
	parsedInit, err := ParseNoiseHandshakeInit(wireInit)
	if err != nil {
		t.Fatalf("ParseNoiseHandshakeInit: %v", err)
	}

	respMsg, bobSession, err := bob.HandleResponderHandshake(context.Background(), parsedInit)
	if err != nil {
		t.Fatalf("HandleResponderHandshake: %v", err)
	}

	wireResp, err := respMsg.MarshalBinary()
	if err != nil {
		t.Fatalf("resp MarshalBinary: %v", err)
	}
	parsedResp, err := ParseNoiseHandshakeResponse(wireResp)
	if err != nil {
		t.Fatalf("ParseNoiseHandshakeResponse: %v", err)
	}

	aliceSession, err := alice.FinishInitiatorHandshake(context.Background(), initState, parsedResp)
	if err != nil {
		t.Fatalf("FinishInitiatorHandshake: %v", err)
	}

	if aliceSession.Mode != HandshakeModeHybrid {
		t.Fatalf("alice mode = %s, want hybrid", aliceSession.Mode)
	}
	if bobSession.Mode != HandshakeModeHybrid {
		t.Fatalf("bob mode = %s, want hybrid", bobSession.Mode)
	}
	if !bytes.Equal(aliceSession.SharedKey, bobSession.SharedKey) {
		t.Fatal("shared keys do not match")
	}
	if aliceSession.PeerID != "bob" {
		t.Fatalf("alice peer = %s, want bob", aliceSession.PeerID)
	}
	if bobSession.PeerID != "alice" {
		t.Fatalf("bob peer = %s, want alice", bobSession.PeerID)
	}
	if aliceSession.PeerSignFingerprint == "" || bobSession.PeerSignFingerprint == "" {
		t.Fatal("expected peer signing fingerprints")
	}
}

func TestHybridNoiseFallsBackToClassical(t *testing.T) {
	slowKEM := slowKEMBackend{
		inner: MLKEM768Backend{},
		delay: 15 * time.Millisecond,
	}

	alice, err := NewHybridNoiseTransport(HybridNoiseConfig{
		NodeID:                 "alice",
		AllowClassicalFallback: true,
	})
	if err != nil {
		t.Fatalf("NewHybridNoiseTransport(alice): %v", err)
	}
	bob, err := NewHybridNoiseTransport(HybridNoiseConfig{
		NodeID:                 "bob",
		KEMBackend:             slowKEM,
		PQCTimeout:             5 * time.Millisecond,
		AllowClassicalFallback: true,
	})
	if err != nil {
		t.Fatalf("NewHybridNoiseTransport(bob): %v", err)
	}

	initState, initMsg, err := alice.StartInitiatorHandshake()
	if err != nil {
		t.Fatalf("StartInitiatorHandshake: %v", err)
	}

	respMsg, bobSession, err := bob.HandleResponderHandshake(context.Background(), initMsg)
	if err != nil {
		t.Fatalf("HandleResponderHandshake: %v", err)
	}
	if respMsg.Mode != HandshakeModeClassicalFallback {
		t.Fatalf("response mode = %s, want classical fallback", respMsg.Mode)
	}

	aliceSession, err := alice.FinishInitiatorHandshake(context.Background(), initState, respMsg)
	if err != nil {
		t.Fatalf("FinishInitiatorHandshake: %v", err)
	}
	if aliceSession.Mode != HandshakeModeClassicalFallback {
		t.Fatalf("alice mode = %s, want classical fallback", aliceSession.Mode)
	}
	if !bytes.Equal(aliceSession.SharedKey, bobSession.SharedKey) {
		t.Fatal("classical fallback keys do not match")
	}
}

func BenchmarkHybridNoiseHandshake(b *testing.B) {
	alice, err := NewHybridNoiseTransport(HybridNoiseConfig{
		NodeID:                 "alice",
		AllowClassicalFallback: true,
	})
	if err != nil {
		b.Fatalf("NewHybridNoiseTransport(alice): %v", err)
	}
	bob, err := NewHybridNoiseTransport(HybridNoiseConfig{
		NodeID:                 "bob",
		AllowClassicalFallback: true,
	})
	if err != nil {
		b.Fatalf("NewHybridNoiseTransport(bob): %v", err)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		initState, initMsg, err := alice.StartInitiatorHandshake()
		if err != nil {
			b.Fatalf("StartInitiatorHandshake: %v", err)
		}
		respMsg, _, err := bob.HandleResponderHandshake(context.Background(), initMsg)
		if err != nil {
			b.Fatalf("HandleResponderHandshake: %v", err)
		}
		if _, err := alice.FinishInitiatorHandshake(context.Background(), initState, respMsg); err != nil {
			b.Fatalf("FinishInitiatorHandshake: %v", err)
		}
	}
}

type slowKEMBackend struct {
	inner KEMBackend
	delay time.Duration
}

func (s slowKEMBackend) Algorithm() string {
	return s.inner.Algorithm()
}

func (s slowKEMBackend) GenerateKeyPair() ([]byte, []byte, error) {
	return s.inner.GenerateKeyPair()
}

func (s slowKEMBackend) Encapsulate(publicKey []byte) ([]byte, []byte, error) {
	time.Sleep(s.delay)
	return s.inner.Encapsulate(publicKey)
}

func (s slowKEMBackend) Decapsulate(privateKey, ciphertext []byte) ([]byte, error) {
	return s.inner.Decapsulate(privateKey, ciphertext)
}
