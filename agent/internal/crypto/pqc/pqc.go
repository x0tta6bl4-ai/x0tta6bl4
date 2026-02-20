// Package pqc implements Post-Quantum Cryptography for mesh tunnels.
// Uses ML-KEM-768 (Kyber) for key exchange + AES-256-GCM for data.
// Wire-compatible with Python pqc_tunnel.py handshake format.
package pqc

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"io"
	"log/slog"
	"sync"

	"github.com/cloudflare/circl/kem/mlkem/mlkem768"
	"golang.org/x/crypto/hkdf"
)

// PQCAvailable indicates whether real PQC crypto is available.
var PQCAvailable = true

// KeyPair holds a PQC key pair.
type KeyPair struct {
	PublicKey  []byte
	PrivateKey []byte
	NodeID     string
	Algorithm  string
}

// SessionKey holds an established session between two peers.
type SessionKey struct {
	PeerID    string
	SharedKey []byte // 32 bytes for AES-256
	AEAD      cipher.AEAD
}

// TunnelManager manages PQC tunnels to multiple peers.
type TunnelManager struct {
	mu       sync.RWMutex
	nodeID   string
	keys     *KeyPair
	sessions map[string]*SessionKey
	logger   *slog.Logger
}

// NewTunnelManager creates a new tunnel manager with generated ML-KEM-768 keys.
func NewTunnelManager(nodeID string) (*TunnelManager, error) {
	pk, sk, err := mlkem768.GenerateKeyPair(rand.Reader)
	if err != nil {
		return nil, fmt.Errorf("generate ML-KEM-768 keys: %w", err)
	}

	pubBytes := make([]byte, mlkem768.PublicKeySize)
	privBytes := make([]byte, mlkem768.PrivateKeySize)
	pk.Pack(pubBytes)
	sk.Pack(privBytes)

	keys := &KeyPair{
		PublicKey:  pubBytes,
		PrivateKey: privBytes,
		NodeID:     nodeID,
		Algorithm:  "ML-KEM-768",
	}

	return &TunnelManager{
		nodeID:   nodeID,
		keys:     keys,
		sessions: make(map[string]*SessionKey),
		logger:   slog.Default().With("component", "pqc"),
	}, nil
}

// GetPublicKey returns the public key for sharing with peers.
func (tm *TunnelManager) GetPublicKey() []byte {
	return tm.keys.PublicKey
}

// CreateHandshakeInit creates a message for initiating a handshake.
// Format: [node_id_len:2][node_id][public_key]
func (tm *TunnelManager) CreateHandshakeInit() []byte {
	nodeIDBytes := []byte(tm.nodeID)
	msg := make([]byte, 2+len(nodeIDBytes)+len(tm.keys.PublicKey))
	binary.BigEndian.PutUint16(msg[0:2], uint16(len(nodeIDBytes)))
	copy(msg[2:], nodeIDBytes)
	copy(msg[2+len(nodeIDBytes):], tm.keys.PublicKey)
	return msg
}

// ProcessHandshakeInit processes an incoming handshake init and returns a response.
// Returns: peerNodeID, sharedSecret, responseMessage, error
func (tm *TunnelManager) ProcessHandshakeInit(data []byte) (string, []byte, []byte, error) {
	if len(data) < 2 {
		return "", nil, nil, fmt.Errorf("handshake message too short")
	}

	nodeIDLen := int(binary.BigEndian.Uint16(data[0:2]))
	if len(data) < 2+nodeIDLen+mlkem768.PublicKeySize {
		return "", nil, nil, fmt.Errorf("handshake message truncated")
	}

	peerID := string(data[2 : 2+nodeIDLen])
	peerPubKeyBytes := data[2+nodeIDLen : 2+nodeIDLen+mlkem768.PublicKeySize]

	var peerPK mlkem768.PublicKey
	if err := peerPK.Unpack(peerPubKeyBytes); err != nil {
		return "", nil, nil, fmt.Errorf("invalid peer public key: %w", err)
	}

	// Encapsulate: generate CT and SS
	ct := make([]byte, mlkem768.CiphertextSize)
	ss := make([]byte, mlkem768.SharedKeySize)
	peerPK.EncapsulateTo(ct, ss, nil) // nil seed for random

	// Derive AES-256 key using HKDF (compatible with Python)
	derivedKey, err := tm.deriveKey(ss)
	if err != nil {
		return "", nil, nil, fmt.Errorf("derive key: %w", err)
	}

	// Create AES-256-GCM AEAD
	block, err := aes.NewCipher(derivedKey)
	if err != nil {
		return "", nil, nil, fmt.Errorf("create cipher: %w", err)
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		return peerID, ss, nil, fmt.Errorf("create GCM: %w", err)
	}

	tm.mu.Lock()
	tm.sessions[peerID] = &SessionKey{
		PeerID:    peerID,
		SharedKey: derivedKey,
		AEAD:      aead,
	}
	tm.mu.Unlock()

	// Create response: [node_id_len:2][node_id][ciphertext]
	ourIDBytes := []byte(tm.nodeID)
	resp := make([]byte, 2+len(ourIDBytes)+len(ct))
	binary.BigEndian.PutUint16(resp[0:2], uint16(len(ourIDBytes)))
	copy(resp[2:], ourIDBytes)
	copy(resp[2+len(ourIDBytes):], ct)

	tm.logger.Info("PQC handshake initiated", "peer", peerID)
	return peerID, ss, resp, nil
}

// ProcessHandshakeResponse processes a response to our initiation.
// Returns: peerNodeID, sharedSecret, error
func (tm *TunnelManager) ProcessHandshakeResponse(data []byte) (string, []byte, error) {
	if len(data) < 2 {
		return "", nil, fmt.Errorf("handshake response too short")
	}

	nodeIDLen := int(binary.BigEndian.Uint16(data[0:2]))
	if len(data) < 2+nodeIDLen+mlkem768.CiphertextSize {
		return "", nil, fmt.Errorf("handshake response truncated")
	}

	peerID := string(data[2 : 2+nodeIDLen])
	ct := data[2+nodeIDLen : 2+nodeIDLen+mlkem768.CiphertextSize]

	var sk mlkem768.PrivateKey
	if err := sk.Unpack(tm.keys.PrivateKey); err != nil {
		return "", nil, fmt.Errorf("invalid local private key: %w", err)
	}

	// Decapsulate: recover SS from CT
	ss := make([]byte, mlkem768.SharedKeySize)
	sk.DecapsulateTo(ss, ct)

	// Derive AES-256 key using HKDF (compatible with Python)
	derivedKey, err := tm.deriveKey(ss)
	if err != nil {
		return "", nil, fmt.Errorf("derive key: %w", err)
	}

	// Create AES-256-GCM AEAD
	block, err := aes.NewCipher(derivedKey)
	if err != nil {
		return "", nil, fmt.Errorf("create cipher: %w", err)
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		return peerID, ss, fmt.Errorf("create GCM: %w", err)
	}

	tm.mu.Lock()
	tm.sessions[peerID] = &SessionKey{
		PeerID:    peerID,
		SharedKey: derivedKey,
		AEAD:      aead,
	}
	tm.mu.Unlock()

	tm.logger.Info("PQC session established", "peer", peerID)
	return peerID, ss, nil
}

// deriveKey uses HKDF to derive a 32-byte AES-256 key from a shared secret.
func (tm *TunnelManager) deriveKey(sharedSecret []byte) ([]byte, error) {
	kdf := hkdf.New(sha256.New, sharedSecret, nil, []byte("x0tta6bl4-pqc-tunnel-v1"))
	derivedKey := make([]byte, 32)
	if _, err := io.ReadFull(kdf, derivedKey); err != nil {
		return nil, err
	}
	return derivedKey, nil
}

// Encrypt encrypts data for a peer. Package framing (PQC1 magic) is NOT applied here.
func (tm *TunnelManager) Encrypt(data []byte, peerID string) ([]byte, error) {
	tm.mu.RLock()
	session, ok := tm.sessions[peerID]
	tm.mu.RUnlock()

	if !ok {
		return nil, fmt.Errorf("no session with peer: %s", peerID)
	}

	nonce := make([]byte, session.AEAD.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, fmt.Errorf("generate nonce: %w", err)
	}

	// Encrypt: nonce || ciphertext
	ciphertext := session.AEAD.Seal(nonce, nonce, data, nil)
	return ciphertext, nil
}

// Decrypt decrypts data from a peer.
func (tm *TunnelManager) Decrypt(data []byte, peerID string) ([]byte, error) {
	tm.mu.RLock()
	session, ok := tm.sessions[peerID]
	tm.mu.RUnlock()

	if !ok {
		return nil, fmt.Errorf("no session with peer: %s", peerID)
	}

	nonceSize := session.AEAD.NonceSize()
	if len(data) < nonceSize {
		return nil, fmt.Errorf("ciphertext too short")
	}

	nonce := data[:nonceSize]
	ciphertext := data[nonceSize:]

	plaintext, err := session.AEAD.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, fmt.Errorf("decrypt: %w", err)
	}

	return plaintext, nil
}

// WrapPacket adds framing to encrypted data: b"PQC1" + [length:4] + encrypted_data
func (tm *TunnelManager) WrapPacket(data []byte, peerID string) ([]byte, error) {
	encrypted, err := tm.Encrypt(data, peerID)
	if err != nil {
		return nil, err
	}

	msg := make([]byte, 8+len(encrypted))
	copy(msg[0:4], "PQC1")
	binary.BigEndian.PutUint32(msg[4:8], uint32(len(encrypted)))
	copy(msg[8:], encrypted)
	return msg, nil
}

// UnwrapPacket validates framing and decrypts data.
func (tm *TunnelManager) UnwrapPacket(data []byte, peerID string) ([]byte, error) {
	if len(data) < 8 || string(data[0:4]) != "PQC1" {
		return nil, fmt.Errorf("invalid PQC packet magic")
	}

	length := binary.BigEndian.Uint32(data[4:8])
	if len(data) < int(8+length) {
		return nil, fmt.Errorf("PQC packet truncated")
	}

	return tm.Decrypt(data[8:8+length], peerID)
}

// HasSession checks if a session exists with a peer.
func (tm *TunnelManager) HasSession(peerID string) bool {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	_, ok := tm.sessions[peerID]
	return ok
}

// RemoveSession removes a session with a peer.
func (tm *TunnelManager) RemoveSession(peerID string) {
	tm.mu.Lock()
	delete(tm.sessions, peerID)
	tm.mu.Unlock()
}
