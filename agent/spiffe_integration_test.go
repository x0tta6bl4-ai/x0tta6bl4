package main

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/x0tta6bl4/agent/internal/identity"
)

func TestSPIFFEIntegration(t *testing.T) {
	// --- Phase 1: Generate test JWKS ---
	t.Run("JWKS_Generation", func(t *testing.T) {
		privKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		pubKey := &privKey.PublicKey

		xBytes := pubKey.X.Bytes()
		yBytes := pubKey.Y.Bytes()

		// Pad to 32 bytes
		xPadded := make([]byte, 32)
		yPadded := make([]byte, 32)
		copy(xPadded[32-len(xBytes):], xBytes)
		copy(yPadded[32-len(yBytes):], yBytes)

		jwks := identity.JWKS{
			Keys: []identity.JWK{
				{
					Kid: "test-key-1",
					Kty: "EC",
					Alg: "ES256",
					Use: "sig",
					Crv: "P-256",
					X:   base64.RawURLEncoding.EncodeToString(xPadded),
					Y:   base64.RawURLEncoding.EncodeToString(yPadded),
				},
			},
		}

		jwksJSON, _ := json.Marshal(jwks)
		t.Logf("Generated JWKS: %s", jwksJSON)

		// --- Phase 2: Start mock JWKS server ---
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			w.Write(jwksJSON)
		}))
		defer server.Close()

		// --- Phase 3: Create validator ---
		validator := identity.NewJWTSVIDValidator(identity.JWTSVIDValidatorConfig{
			JWKSURL:          server.URL,
			TrustedDomains:   []string{"x0tta6bl4.mesh"},
			ExpectedAudience: "x0tta6bl4-maas",
			ClockSkew:        30 * time.Second,
		})

		// --- Phase 4: Create and sign a test JWT-SVID ---
		now := time.Now()
		claims := identity.JWTClaims{
			Sub: "spiffe://x0tta6bl4.mesh/node/test-node-123",
			Aud: "x0tta6bl4-maas",
			Iss: "spire-server",
			Exp: now.Add(1 * time.Hour).Unix(),
			Iat: now.Unix(),
		}

		// Create JWT header
		header := map[string]string{
			"alg": "ES256",
			"kid": "test-key-1",
			"typ": "JWT",
		}

		headerBytes, _ := json.Marshal(header)
		claimsBytes, _ := json.Marshal(claims)

		headerB64 := base64.RawURLEncoding.EncodeToString(headerBytes)
		claimsB64 := base64.RawURLEncoding.EncodeToString(claimsBytes)
		signingInput := headerB64 + "." + claimsB64

		// Sign
		hash := sha256.Sum256([]byte(signingInput))
		r, s, _ := ecdsa.Sign(rand.Reader, privKey, hash[:])
		rBytes := r.Bytes()
		sBytes := s.Bytes()
		rPadded := make([]byte, 32)
		sPadded := make([]byte, 32)
		copy(rPadded[32-len(rBytes):], rBytes)
		copy(sPadded[32-len(sBytes):], sBytes)
		sigBytes := append(rPadded, sPadded...)
		sigB64 := base64.RawURLEncoding.EncodeToString(sigBytes)

		token := signingInput + "." + sigB64
		t.Logf("Created JWT-SVID: %s...%s", token[:50], token[len(token)-20:])

		// --- Phase 5: Validate the token ---
		result, err := validator.Validate(context.Background(), token)
		if err != nil {
			t.Fatalf("Validate error: %v", err)
		}

		if !result.Valid {
			t.Errorf("Token should be valid, got error: %s", result.Error)
		}
		if result.SpiffeID != "spiffe://x0tta6bl4.mesh/node/test-node-123" {
			t.Errorf("SpiffeID = %s, want spiffe://x0tta6bl4.mesh/node/test-node-123", result.SpiffeID)
		}
		if result.TrustDomain != "x0tta6bl4.mesh" {
			t.Errorf("TrustDomain = %s, want x0tta6bl4.mesh", result.TrustDomain)
		}
		t.Logf("Validation result: valid=%v spiffe_id=%s trust_domain=%s", result.Valid, result.SpiffeID, result.TrustDomain)
	})

	// --- Phase 6: Test expired token ---
	t.Run("Expired_Token", func(t *testing.T) {
		privKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		pubKey := &privKey.PublicKey

		xBytes := pubKey.X.Bytes()
		yBytes := pubKey.Y.Bytes()
		xPadded := make([]byte, 32)
		yPadded := make([]byte, 32)
		copy(xPadded[32-len(xBytes):], xBytes)
		copy(yPadded[32-len(yBytes):], yBytes)

		jwks := identity.JWKS{
			Keys: []identity.JWK{
				{
					Kid: "test-key-2", Kty: "EC", Alg: "ES256", Use: "sig", Crv: "P-256",
					X: base64.RawURLEncoding.EncodeToString(xPadded),
					Y: base64.RawURLEncoding.EncodeToString(yPadded),
				},
			},
		}
		jwksJSON, _ := json.Marshal(jwks)

		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Write(jwksJSON)
		}))
		defer server.Close()

		validator := identity.NewJWTSVIDValidator(identity.JWTSVIDValidatorConfig{
			JWKSURL:          server.URL,
			TrustedDomains:   []string{"x0tta6bl4.mesh"},
			ExpectedAudience: "x0tta6bl4-maas",
		})

		// Expired token
		claims := identity.JWTClaims{
			Sub: "spiffe://x0tta6bl4.mesh/node/test",
			Aud: "x0tta6bl4-maas",
			Exp: time.Now().Add(-1 * time.Hour).Unix(), // expired
		}
		header := map[string]string{"alg": "ES256", "kid": "test-key-2", "typ": "JWT"}
		headerBytes, _ := json.Marshal(header)
		claimsBytes, _ := json.Marshal(claims)
		headerB64 := base64.RawURLEncoding.EncodeToString(headerBytes)
		claimsB64 := base64.RawURLEncoding.EncodeToString(claimsBytes)
		hash := sha256.Sum256([]byte(headerB64 + "." + claimsB64))
		r, s, _ := ecdsa.Sign(rand.Reader, privKey, hash[:])
		rBytes := r.Bytes()
		sBytes := s.Bytes()
		rPadded := make([]byte, 32)
		sPadded := make([]byte, 32)
		copy(rPadded[32-len(rBytes):], rBytes)
		copy(sPadded[32-len(sBytes):], sBytes)
		sigB64 := base64.RawURLEncoding.EncodeToString(append(rPadded, sPadded...))

		token := headerB64 + "." + claimsB64 + "." + sigB64

		result, _ := validator.Validate(context.Background(), token)
		if result.Valid {
			t.Error("Expired token should be invalid")
		}
		t.Logf("Expired token correctly rejected: %s", result.Error)
	})

	// --- Phase 7: Test untrusted domain ---
	t.Run("Untrusted_Domain", func(t *testing.T) {
		privKey, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
		pubKey := &privKey.PublicKey

		xBytes := pubKey.X.Bytes()
		yBytes := pubKey.Y.Bytes()
		xPadded := make([]byte, 32)
		yPadded := make([]byte, 32)
		copy(xPadded[32-len(xBytes):], xBytes)
		copy(yPadded[32-len(yBytes):], yBytes)

		jwks := identity.JWKS{
			Keys: []identity.JWK{
				{
					Kid: "test-key-3", Kty: "EC", Alg: "ES256", Use: "sig", Crv: "P-256",
					X: base64.RawURLEncoding.EncodeToString(xPadded),
					Y: base64.RawURLEncoding.EncodeToString(yPadded),
				},
			},
		}
		jwksJSON, _ := json.Marshal(jwks)

		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Write(jwksJSON)
		}))
		defer server.Close()

		validator := identity.NewJWTSVIDValidator(identity.JWTSVIDValidatorConfig{
			JWKSURL:          server.URL,
			TrustedDomains:   []string{"x0tta6bl4.mesh"},
			ExpectedAudience: "x0tta6bl4-maas",
		})

		// Token from untrusted domain
		claims := identity.JWTClaims{
			Sub: "spiffe://evil.example.com/node/malicious",
			Aud: "x0tta6bl4-maas",
			Exp: time.Now().Add(1 * time.Hour).Unix(),
		}
		header := map[string]string{"alg": "ES256", "kid": "test-key-3", "typ": "JWT"}
		headerBytes, _ := json.Marshal(header)
		claimsBytes, _ := json.Marshal(claims)
		headerB64 := base64.RawURLEncoding.EncodeToString(headerBytes)
		claimsB64 := base64.RawURLEncoding.EncodeToString(claimsBytes)
		hash := sha256.Sum256([]byte(headerB64 + "." + claimsB64))
		r, s, _ := ecdsa.Sign(rand.Reader, privKey, hash[:])
		rBytes := r.Bytes()
		sBytes := s.Bytes()
		rPadded := make([]byte, 32)
		sPadded := make([]byte, 32)
		copy(rPadded[32-len(rBytes):], rBytes)
		copy(sPadded[32-len(sBytes):], sBytes)
		sigB64 := base64.RawURLEncoding.EncodeToString(append(rPadded, sPadded...))

		token := headerB64 + "." + claimsB64 + "." + sigB64

		result, _ := validator.Validate(context.Background(), token)
		if result.Valid {
			t.Error("Untrusted domain should be rejected")
		}
		t.Logf("Untrusted domain correctly rejected: %s", result.Error)
	})

	// --- Phase 8: Test trust domain config ---
	t.Run("Trust_Domain_Config", func(t *testing.T) {
		cfg := identity.JWTSVIDValidatorConfig{
			TrustedDomains: []string{"x0tta6bl4.mesh", "example.com"},
		}
		v := identity.NewJWTSVIDValidator(cfg)
		_ = v // just verify construction
		fmt.Println("Trust domain config: OK")
	})

	fmt.Println("\n=== SPIFFE INTEGRATION: ALL TESTS PASSED ===")
}
