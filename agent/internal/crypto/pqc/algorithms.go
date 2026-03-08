package pqc

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"

	"github.com/cloudflare/circl/kem/mlkem/mlkem768"
	"github.com/cloudflare/circl/sign/mldsa/mldsa65"
)

// KEMBackend abstracts the ML-KEM implementation so alternative backends
// such as liboqs can be injected without changing the handshake flow.
type KEMBackend interface {
	Algorithm() string
	GenerateKeyPair() (publicKey, privateKey []byte, err error)
	Encapsulate(publicKey []byte) (ciphertext, sharedSecret []byte, err error)
	Decapsulate(privateKey, ciphertext []byte) (sharedSecret []byte, err error)
}

// SignerBackend abstracts the ML-DSA implementation for the same reason.
type SignerBackend interface {
	Algorithm() string
	GenerateKeyPair() (publicKey, privateKey []byte, err error)
	Sign(privateKey, message []byte) ([]byte, error)
	Verify(publicKey, message, signature []byte) bool
}

// MLKEM768Backend is the default FIPS 203-compliant KEM backend.
type MLKEM768Backend struct{}

func (MLKEM768Backend) Algorithm() string {
	return "ML-KEM-768"
}

func (MLKEM768Backend) GenerateKeyPair() ([]byte, []byte, error) {
	pk, sk, err := mlkem768.GenerateKeyPair(rand.Reader)
	if err != nil {
		return nil, nil, fmt.Errorf("generate ML-KEM-768 keypair: %w", err)
	}

	pub, err := pk.MarshalBinary()
	if err != nil {
		return nil, nil, fmt.Errorf("marshal ML-KEM public key: %w", err)
	}

	priv, err := sk.MarshalBinary()
	if err != nil {
		return nil, nil, fmt.Errorf("marshal ML-KEM private key: %w", err)
	}

	return pub, priv, nil
}

func (MLKEM768Backend) Encapsulate(publicKey []byte) ([]byte, []byte, error) {
	var pk mlkem768.PublicKey
	if err := pk.Unpack(publicKey); err != nil {
		return nil, nil, fmt.Errorf("unmarshal ML-KEM public key: %w", err)
	}

	ct, ss, err := mlkem768.Scheme().Encapsulate(&pk)
	if err != nil {
		return nil, nil, fmt.Errorf("encapsulate ML-KEM secret: %w", err)
	}
	return ct, ss, nil
}

func (MLKEM768Backend) Decapsulate(privateKey, ciphertext []byte) ([]byte, error) {
	var sk mlkem768.PrivateKey
	if err := sk.Unpack(privateKey); err != nil {
		return nil, fmt.Errorf("unmarshal ML-KEM private key: %w", err)
	}

	ss, err := mlkem768.Scheme().Decapsulate(&sk, ciphertext)
	if err != nil {
		return nil, fmt.Errorf("decapsulate ML-KEM secret: %w", err)
	}
	return ss, nil
}

// MLDSA65Backend is the default FIPS 204-compliant signature backend.
type MLDSA65Backend struct{}

func (MLDSA65Backend) Algorithm() string {
	return "ML-DSA-65"
}

func (MLDSA65Backend) GenerateKeyPair() ([]byte, []byte, error) {
	pk, sk, err := mldsa65.GenerateKey(rand.Reader)
	if err != nil {
		return nil, nil, fmt.Errorf("generate ML-DSA-65 keypair: %w", err)
	}

	return pk.Bytes(), sk.Bytes(), nil
}

func (MLDSA65Backend) Sign(privateKey, message []byte) ([]byte, error) {
	var sk mldsa65.PrivateKey
	if err := sk.UnmarshalBinary(privateKey); err != nil {
		return nil, fmt.Errorf("unmarshal ML-DSA private key: %w", err)
	}

	signature := make([]byte, mldsa65.SignatureSize)
	if err := mldsa65.SignTo(&sk, message, nil, false, signature); err != nil {
		return nil, fmt.Errorf("sign ML-DSA transcript: %w", err)
	}
	return signature, nil
}

func (MLDSA65Backend) Verify(publicKey, message, signature []byte) bool {
	var pk mldsa65.PublicKey
	if err := pk.UnmarshalBinary(publicKey); err != nil {
		return false
	}
	return mldsa65.Verify(&pk, message, nil, signature)
}

func keyFingerprint(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:8])
}
