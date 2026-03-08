package pqc

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// KeyStore defines the interface for durable PQC material storage.
type KeyStore interface {
	Load(ctx context.Context) (*RotationSnapshot, error)
	Save(ctx context.Context, snapshot RotationSnapshot) error
}

const (

	DefaultKEMRotationInterval       = 30 * 24 * time.Hour
	DefaultSignatureRotationInterval = 90 * 24 * time.Hour
	DefaultOverlapPeriod             = 7 * 24 * time.Hour
)

// RotationPolicy controls PQC key lifetimes and overlap windows.
type RotationPolicy struct {
	KEMRotationInterval       time.Duration
	SignatureRotationInterval time.Duration
	OverlapPeriod             time.Duration
	BackupAlgorithm           string
	Clock                     func() time.Time
}

// VersionedKeyMaterial captures one active or overlapping key generation.
type VersionedKeyMaterial struct {
	KeyID       string
	Algorithm   string
	PublicKey   []byte
	PrivateKey  []byte
	CreatedAt   time.Time
	RotateAfter time.Time
	AcceptUntil time.Time
}

// BackupKeyReference models externally generated NTRU recovery keys stored in
// Kubernetes Secrets for disaster recovery.
type BackupKeyReference struct {
	Algorithm  string
	SecretName string
	PublicKey  []byte
	PrivateKey []byte
	LoadedAt   time.Time
}

// RotationEvent reports a completed key rotation.
type RotationEvent struct {
	KeyType     string
	PreviousKey string
	CurrentKey  string
	RotatedAt   time.Time
}

// RotationSnapshot is safe to hand to callers without exposing internal state.
type RotationSnapshot struct {
	ActiveKEM        VersionedKeyMaterial
	AcceptedKEM      []VersionedKeyMaterial
	ActiveSignature  VersionedKeyMaterial
	AcceptedSigners  []VersionedKeyMaterial
	BackupReferences []BackupKeyReference
}

// RotationManager manages KEM/signing rotation and the overlap window that
// allows old and new keys to coexist without dropping sessions.
type RotationManager struct {
	mu            sync.RWMutex
	policy        RotationPolicy
	kemBackend    KEMBackend
	signerBackend SignerBackend

	activeKEM       VersionedKeyMaterial
	activeSignature VersionedKeyMaterial
	previousKEM     []VersionedKeyMaterial
	previousSigners []VersionedKeyMaterial
	backupKeys      []BackupKeyReference
}

// NewRotationManager creates active ML-KEM and ML-DSA identities.
// If store is provided, it attempts to bootstrap material from durable storage.
func NewRotationManager(ctx context.Context, policy RotationPolicy, kemBackend KEMBackend, signerBackend SignerBackend, store KeyStore) (*RotationManager, error) {
	if kemBackend == nil {
		kemBackend = MLKEM768Backend{}
	}
	if signerBackend == nil {
		signerBackend = MLDSA65Backend{}
	}
	if policy.Clock == nil {
		policy.Clock = time.Now
	}
	// ... defaults ...
	if policy.KEMRotationInterval <= 0 {
		policy.KEMRotationInterval = DefaultKEMRotationInterval
	}
	if policy.SignatureRotationInterval <= 0 {
		policy.SignatureRotationInterval = DefaultSignatureRotationInterval
	}
	if policy.OverlapPeriod <= 0 {
		policy.OverlapPeriod = DefaultOverlapPeriod
	}
	if policy.BackupAlgorithm == "" {
		policy.BackupAlgorithm = "NTRU-HRSS-701"
	}

	m := &RotationManager{
		policy:        policy,
		kemBackend:    kemBackend,
		signerBackend: signerBackend,
	}

	if store != nil {
		snapshot, err := store.Load(ctx)
		if err == nil && snapshot != nil {
			m.activeKEM = snapshot.ActiveKEM
			m.activeSignature = snapshot.ActiveSignature
			m.previousKEM = snapshot.AcceptedKEM
			m.previousSigners = snapshot.AcceptedSigners
			m.backupKeys = snapshot.BackupReferences
			return m, nil
		}
	}

	now := policy.Clock()
	activeKEM, err := generateVersionedKey(kemBackend, policy.KEMRotationInterval, now)
	if err != nil {
		return nil, err
	}
	activeSignature, err := generateVersionedKey(signerBackend, policy.SignatureRotationInterval, now)
	if err != nil {
		return nil, err
	}

	m.activeKEM = activeKEM
	m.activeSignature = activeSignature

	if store != nil {
		_ = store.Save(ctx, m.Snapshot(now))
	}

	return m, nil
}
// RotateDue rotates keys that are past their interval and preserves the old
// generation for the configured overlap period.
func (m *RotationManager) RotateDue(now time.Time) ([]RotationEvent, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.cleanupExpiredLocked(now)
	var events []RotationEvent

	if !now.Before(m.activeKEM.RotateAfter) {
		next, err := generateVersionedKey(m.kemBackend, m.policy.KEMRotationInterval, now)
		if err != nil {
			return nil, err
		}
		old := m.activeKEM
		old.AcceptUntil = now.Add(m.policy.OverlapPeriod)
		m.previousKEM = append([]VersionedKeyMaterial{old}, m.previousKEM...)
		m.activeKEM = next
		events = append(events, RotationEvent{
			KeyType:     "kem",
			PreviousKey: old.KeyID,
			CurrentKey:  next.KeyID,
			RotatedAt:   now,
		})
	}

	if !now.Before(m.activeSignature.RotateAfter) {
		next, err := generateVersionedKey(m.signerBackend, m.policy.SignatureRotationInterval, now)
		if err != nil {
			return nil, err
		}
		old := m.activeSignature
		old.AcceptUntil = now.Add(m.policy.OverlapPeriod)
		m.previousSigners = append([]VersionedKeyMaterial{old}, m.previousSigners...)
		m.activeSignature = next
		events = append(events, RotationEvent{
			KeyType:     "signature",
			PreviousKey: old.KeyID,
			CurrentKey:  next.KeyID,
			RotatedAt:   now,
		})
	}

	return events, nil
}

// CurrentIdentity returns the active material to advertise in new handshakes.
func (m *RotationManager) CurrentIdentity(nodeID string) HybridIdentity {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return HybridIdentity{
		NodeID:             nodeID,
		KEMAlgorithm:       m.activeKEM.Algorithm,
		KEMPublicKey:       cloneBytes(m.activeKEM.PublicKey),
		KEMPrivateKey:      cloneBytes(m.activeKEM.PrivateKey),
		SignatureAlgorithm: m.activeSignature.Algorithm,
		SignPublicKey:      cloneBytes(m.activeSignature.PublicKey),
		SignPrivateKey:     cloneBytes(m.activeSignature.PrivateKey),
	}
}

// Snapshot returns the active keys plus all overlapping previous generations.
func (m *RotationManager) Snapshot(now time.Time) RotationSnapshot {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.cleanupExpiredLocked(now)
	return RotationSnapshot{
		ActiveKEM:        cloneVersionedKey(m.activeKEM),
		AcceptedKEM:      cloneVersionedKeySlice(append([]VersionedKeyMaterial{m.activeKEM}, m.previousKEM...)),
		ActiveSignature:  cloneVersionedKey(m.activeSignature),
		AcceptedSigners:  cloneVersionedKeySlice(append([]VersionedKeyMaterial{m.activeSignature}, m.previousSigners...)),
		BackupReferences: cloneBackupRefs(m.backupKeys),
	}
}

// RegisterNTRUBackup registers externally managed NTRU recovery material.
func (m *RotationManager) RegisterNTRUBackup(secretName string, publicKey, privateKey []byte) error {
	if secretName == "" {
		return fmt.Errorf("secret name is required")
	}
	if len(publicKey) == 0 || len(privateKey) == 0 {
		return fmt.Errorf("backup key material is required")
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	m.backupKeys = append(m.backupKeys, BackupKeyReference{
		Algorithm:  m.policy.BackupAlgorithm,
		SecretName: secretName,
		PublicKey:  cloneBytes(publicKey),
		PrivateKey: cloneBytes(privateKey),
		LoadedAt:   m.policy.Clock(),
	})
	return nil
}

// AcceptsKEMPublicKey reports whether a public key is active or still within
// the overlap window.
func (m *RotationManager) AcceptsKEMPublicKey(publicKey []byte, now time.Time) bool {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.cleanupExpiredLocked(now)
	if equalBytes(m.activeKEM.PublicKey, publicKey) {
		return true
	}
	for _, key := range m.previousKEM {
		if equalBytes(key.PublicKey, publicKey) {
			return true
		}
	}
	return false
}

// AcceptsSignaturePublicKey reports whether a signing key is active or
// preserved during the overlap window.
func (m *RotationManager) AcceptsSignaturePublicKey(publicKey []byte, now time.Time) bool {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.cleanupExpiredLocked(now)
	if equalBytes(m.activeSignature.PublicKey, publicKey) {
		return true
	}
	for _, key := range m.previousSigners {
		if equalBytes(key.PublicKey, publicKey) {
			return true
		}
	}
	return false
}

func (m *RotationManager) cleanupExpiredLocked(now time.Time) {
	m.previousKEM = filterAcceptedKeys(m.previousKEM, now)
	m.previousSigners = filterAcceptedKeys(m.previousSigners, now)
}

func filterAcceptedKeys(keys []VersionedKeyMaterial, now time.Time) []VersionedKeyMaterial {
	filtered := keys[:0]
	for _, key := range keys {
		if key.AcceptUntil.IsZero() || !now.After(key.AcceptUntil) {
			filtered = append(filtered, key)
		}
	}
	return filtered
}

type keyGenerator interface {
	Algorithm() string
	GenerateKeyPair() (publicKey, privateKey []byte, err error)
}

func generateVersionedKey(generator keyGenerator, interval time.Duration, now time.Time) (VersionedKeyMaterial, error) {
	publicKey, privateKey, err := generator.GenerateKeyPair()
	if err != nil {
		return VersionedKeyMaterial{}, fmt.Errorf("generate %s key material: %w", generator.Algorithm(), err)
	}

	return VersionedKeyMaterial{
		KeyID:       keyFingerprint(publicKey),
		Algorithm:   generator.Algorithm(),
		PublicKey:   publicKey,
		PrivateKey:  privateKey,
		CreatedAt:   now,
		RotateAfter: now.Add(interval),
	}, nil
}

func cloneVersionedKey(key VersionedKeyMaterial) VersionedKeyMaterial {
	return VersionedKeyMaterial{
		KeyID:       key.KeyID,
		Algorithm:   key.Algorithm,
		PublicKey:   cloneBytes(key.PublicKey),
		PrivateKey:  cloneBytes(key.PrivateKey),
		CreatedAt:   key.CreatedAt,
		RotateAfter: key.RotateAfter,
		AcceptUntil: key.AcceptUntil,
	}
}

func cloneVersionedKeySlice(keys []VersionedKeyMaterial) []VersionedKeyMaterial {
	out := make([]VersionedKeyMaterial, 0, len(keys))
	for _, key := range keys {
		out = append(out, cloneVersionedKey(key))
	}
	return out
}

func cloneBackupRefs(keys []BackupKeyReference) []BackupKeyReference {
	out := make([]BackupKeyReference, 0, len(keys))
	for _, key := range keys {
		out = append(out, BackupKeyReference{
			Algorithm:  key.Algorithm,
			SecretName: key.SecretName,
			PublicKey:  cloneBytes(key.PublicKey),
			PrivateKey: cloneBytes(key.PrivateKey),
			LoadedAt:   key.LoadedAt,
		})
	}
	return out
}

func equalBytes(a, b []byte) bool {
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
