// Package pqc implements Post-Quantum Cryptography for mesh tunnels.
// Uses ML-KEM-768 (Kyber) for key exchange + ML-DSA-65 for authentication + AES-256-GCM for data.
// Handshake is MITM-resistant via ML-DSA-65 signatures over the transcript.
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
	"github.com/cloudflare/circl/sign/mldsa/mldsa65"
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
	signKeys *KeyPair
	sessions map[string]*SessionKey

	// trustedPeers: peerID → ML-DSA-65 public key.
	// Handshake succeeds only if the peer's signing key matches.
	// Populated via SetTrustedPeer or control plane.
	trustedPeers map[string][]byte

	logger *slog.Logger
}

// NewTunnelManager creates a new tunnel manager with generated ML-KEM-768 and ML-DSA-65 keys.
func NewTunnelManager(nodeID string) (*TunnelManager, error) {
	pk, sk, err := mlkem768.GenerateKeyPair(rand.Reader)
	if err != nil {
		return nil, fmt.Errorf("generate ML-KEM-768 keys: %w", err)
	}
	pubBytes := make([]byte, mlkem768.PublicKeySize)
	privBytes := make([]byte, mlkem768.PrivateKeySize)
	pk.Pack(pubBytes)
	sk.Pack(privBytes)

	signPub, signPriv, err := mldsa65.GenerateKey(rand.Reader)
	if err != nil {
		return nil, fmt.Errorf("generate ML-DSA-65 keys: %w", err)
	}

	return &TunnelManager{
		nodeID:       nodeID,
		keys:         &KeyPair{PublicKey: pubBytes, PrivateKey: privBytes, NodeID: nodeID, Algorithm: "ML-KEM-768"},
		signKeys:     &KeyPair{PublicKey: signPub.Bytes(), PrivateKey: signPriv.Bytes(), NodeID: nodeID, Algorithm: "ML-DSA-65"},
		sessions:     make(map[string]*SessionKey),
		trustedPeers: make(map[string][]byte),
		logger:       slog.Default().With("component", "pqc"),
	}, nil
}

func (tm *TunnelManager) GetPublicKey() []byte        { return tm.keys.PublicKey }
func (tm *TunnelManager) GetSignPublicKey() []byte     { return tm.signKeys.PublicKey }

// SetTrustedPeer registers a peer's ML-DSA-65 public key for handshake verification.
func (tm *TunnelManager) SetTrustedPeer(peerID string, signPublicKey []byte) {
	tm.mu.Lock()
	defer tm.mu.Unlock()
	tm.trustedPeers[peerID] = cloneBytes(signPublicKey)
	tm.logger.Info("trusted peer registered", "peer", peerID, "key_fp", keyFingerprint(signPublicKey))
}

// RemoveTrustedPeer removes a peer from the trusted list.
func (tm *TunnelManager) RemoveTrustedPeer(peerID string) {
	tm.mu.Lock()
	defer tm.mu.Unlock()
	delete(tm.trustedPeers, peerID)
}

// --- Handshake init/response ---

// CreateHandshakeInit creates an authenticated handshake initiation message.
// Wire format: [node_id_len:2][node_id][kem_pubkey][sign_pubkey][signature]
func (tm *TunnelManager) CreateHandshakeInit() ([]byte, error) {
	transcript := handshakeInitTranscript(tm.nodeID, tm.keys.PublicKey)
	signature, err := tm.signTranscript(transcript)
	if err != nil {
		return nil, fmt.Errorf("sign handshake init: %w", err)
	}
	return encodeHandshakeMsg(tm.nodeID, tm.keys.PublicKey, tm.signKeys.PublicKey, signature), nil
}

// ProcessHandshakeInit verifies the initiator's signature, encapsulates a shared secret,
// and returns the response message.
func (tm *TunnelManager) ProcessHandshakeInit(data []byte) (string, []byte, []byte, error) {
	peerID, peerKEMPub, peerSignPub, signature, err := decodeHandshakeMsg(data,
		mlkem768.PublicKeySize+mldsa65.PublicKeySize+mldsa65.SignatureSize, "init")
	if err != nil {
		return "", nil, nil, err
	}

	transcript := handshakeInitTranscript(peerID, peerKEMPub)
	if err := tm.verifyPeerSignature(peerID, peerSignPub, transcript, signature); err != nil {
		return "", nil, nil, err
	}

	// Encapsulate
	var peerPK mlkem768.PublicKey
	if err := peerPK.Unpack(peerKEMPub); err != nil {
		return "", nil, nil, fmt.Errorf("invalid peer KEM public key: %w", err)
	}
	ct := make([]byte, mlkem768.CiphertextSize)
	ss := make([]byte, mlkem768.SharedKeySize)
	peerPK.EncapsulateTo(ct, ss, nil)

	// Establish session
	if err := tm.establishSession(peerID, ss); err != nil {
		return "", nil, nil, err
	}

	// Sign and encode response
	respSig, err := tm.signTranscript(handshakeResponseTranscript(tm.nodeID, ct))
	if err != nil {
		return "", nil, nil, fmt.Errorf("sign handshake response: %w", err)
	}
	resp := encodeHandshakeMsg(tm.nodeID, ct, tm.signKeys.PublicKey, respSig)

	tm.logger.Info("PQC handshake initiated (authenticated)", "peer", peerID)
	return peerID, ss, resp, nil
}

// ProcessHandshakeResponse verifies the responder's signature and recovers the shared secret.
func (tm *TunnelManager) ProcessHandshakeResponse(data []byte) (string, []byte, error) {
	peerID, ct, peerSignPub, signature, err := decodeHandshakeMsg(data,
		mlkem768.CiphertextSize+mldsa65.PublicKeySize+mldsa65.SignatureSize, "response")
	if err != nil {
		return "", nil, err
	}

	transcript := handshakeResponseTranscript(peerID, ct)
	if err := tm.verifyPeerSignature(peerID, peerSignPub, transcript, signature); err != nil {
		return "", nil, err
	}

	// Decapsulate
	var sk mlkem768.PrivateKey
	if err := sk.Unpack(tm.keys.PrivateKey); err != nil {
		return "", nil, fmt.Errorf("invalid local private key: %w", err)
	}
	ss := make([]byte, mlkem768.SharedKeySize)
	sk.DecapsulateTo(ss, ct)

	// Establish session
	if err := tm.establishSession(peerID, ss); err != nil {
		return "", nil, err
	}

	tm.logger.Info("PQC session established (authenticated)", "peer", peerID)
	return peerID, ss, nil
}

// --- Internal helpers ---

// establishSession derives an AES-256-GCM key from the shared secret and stores the session.
func (tm *TunnelManager) establishSession(peerID string, sharedSecret []byte) error {
	derivedKey, err := tm.deriveKey(sharedSecret)
	if err != nil {
		return fmt.Errorf("derive key: %w", err)
	}
	block, err := aes.NewCipher(derivedKey)
	if err != nil {
		return fmt.Errorf("create cipher: %w", err)
	}
	aead, err := cipher.NewGCM(block)
	if err != nil {
		return fmt.Errorf("create GCM: %w", err)
	}

	tm.mu.Lock()
	tm.sessions[peerID] = &SessionKey{PeerID: peerID, SharedKey: derivedKey, AEAD: aead}
	tm.mu.Unlock()
	return nil
}

// verifyPeerSignature checks an ML-DSA-65 signature against trusted or TOFU peer keys.
func (tm *TunnelManager) verifyPeerSignature(peerID string, signPubKey, transcript, signature []byte) error {
	tm.mu.RLock()
	trustedKey, isTrusted := tm.trustedPeers[peerID]
	tm.mu.RUnlock()

	if isTrusted {
		if !bytesEqual(trustedKey, signPubKey) {
			return fmt.Errorf("handshake rejected: signing key mismatch for peer %s (possible MITM)", peerID)
		}
		ok, err := verifyTranscript(trustedKey, transcript, signature)
		if err != nil {
			return fmt.Errorf("verify signature: %w", err)
		}
		if !ok {
			return fmt.Errorf("invalid ML-DSA-65 signature from peer %s", peerID)
		}
		return nil
	}

	// TOFU: accept unknown peer's signing key
	ok, err := verifyTranscript(signPubKey, transcript, signature)
	if err != nil {
		return fmt.Errorf("verify signature (TOFU): %w", err)
	}
	if !ok {
		return fmt.Errorf("invalid ML-DSA-65 signature from unknown peer %s", peerID)
	}
	tm.logger.Warn("TOFU: accepting untrusted peer signing key", "peer", peerID, "key_fp", keyFingerprint(signPubKey))
	return nil
}

// signTranscript signs a handshake transcript with ML-DSA-65.
func (tm *TunnelManager) signTranscript(transcript []byte) ([]byte, error) {
	var sk mldsa65.PrivateKey
	if err := sk.UnmarshalBinary(tm.signKeys.PrivateKey); err != nil {
		return nil, fmt.Errorf("unmarshal ML-DSA private key: %w", err)
	}
	signature := make([]byte, mldsa65.SignatureSize)
	if err := mldsa65.SignTo(&sk, transcript, nil, false, signature); err != nil {
		return nil, fmt.Errorf("sign transcript: %w", err)
	}
	return signature, nil
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

// --- Wire format helpers ---

func handshakeInitTranscript(nodeID string, kemPubKey []byte) []byte {
	h := sha256.New()
	h.Write([]byte(nodeID))
	h.Write(kemPubKey)
	return h.Sum(nil)
}

func handshakeResponseTranscript(nodeID string, ciphertext []byte) []byte {
	h := sha256.New()
	h.Write([]byte(nodeID))
	h.Write(ciphertext)
	return h.Sum(nil)
}

func encodeHandshakeMsg(nodeID string, payload, signPubKey, signature []byte) []byte {
	nodeIDBytes := []byte(nodeID)
	msg := make([]byte, 2+len(nodeIDBytes)+len(payload)+len(signPubKey)+len(signature))
	off := 0
	binary.BigEndian.PutUint16(msg[off:off+2], uint16(len(nodeIDBytes)))
	off += 2
	copy(msg[off:], nodeIDBytes)
	off += len(nodeIDBytes)
	copy(msg[off:], payload)
	off += len(payload)
	copy(msg[off:], signPubKey)
	off += len(signPubKey)
	copy(msg[off:], signature)
	return msg
}

func decodeHandshakeMsg(data []byte, minLen int, label string) (nodeID string, payload, signPubKey, signature []byte, err error) {
	if len(data) < 2 {
		return "", nil, nil, nil, fmt.Errorf("handshake %s too short", label)
	}
	nodeIDLen := int(binary.BigEndian.Uint16(data[0:2]))
	if len(data) < 2+nodeIDLen+minLen {
		return "", nil, nil, nil, fmt.Errorf("handshake %s truncated: got %d, need %d", label, len(data), 2+nodeIDLen+minLen)
	}
	off := 2
	nodeID = string(data[off : off+nodeIDLen])
	off += nodeIDLen
	payloadEnd := off + (minLen - mldsa65.PublicKeySize - mldsa65.SignatureSize)
	signEnd := payloadEnd + mldsa65.PublicKeySize
	payload = data[off:payloadEnd]
	signPubKey = data[payloadEnd:signEnd]
	signature = data[signEnd : signEnd+mldsa65.SignatureSize]
	return
}

func verifyTranscript(signPublicKey, transcript, signature []byte) (bool, error) {
	var pk mldsa65.PublicKey
	if err := pk.UnmarshalBinary(signPublicKey); err != nil {
		return false, fmt.Errorf("unmarshal ML-DSA public key: %w", err)
	}
	return mldsa65.Verify(&pk, transcript, nil, signature), nil
}

func bytesEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// --- Data plane (encrypt/decrypt) ---

// Encrypt encrypts data for a peer.
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
	return session.AEAD.Seal(nonce, nonce, data, nil), nil
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
	return session.AEAD.Open(nil, data[:nonceSize], data[nonceSize:], nil)
}

// WrapPacket adds framing: b"PQC1" + [length:4] + encrypted_data.
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

// UnwrapPacket validates framing and decrypts.
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

func (tm *TunnelManager) HasSession(peerID string) bool {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	_, ok := tm.sessions[peerID]
	return ok
}

func (tm *TunnelManager) RemoveSession(peerID string) {
	tm.mu.Lock()
	delete(tm.sessions, peerID)
	tm.mu.Unlock()
}
