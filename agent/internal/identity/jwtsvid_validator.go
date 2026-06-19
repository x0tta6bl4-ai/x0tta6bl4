package identity

import (
	"context"
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"time"
)

// JWKS represents a JSON Web Key Set.
type JWKS struct {
	Keys []JWK `json:"keys"`
}

// JWK represents a single JSON Web Key.
type JWK struct {
	Kid string `json:"kid"`
	Kty string `json:"kty"`
	Alg string `json:"alg"`
	Use string `json:"use"`
	N   string `json:"n,omitempty"`
	E   string `json:"e,omitempty"`
	Crv string `json:"crv,omitempty"`
	X   string `json:"x,omitempty"`
	Y   string `json:"y,omitempty"`
}

// JWTClaims represents SPIFFE JWT-SVID claims.
type JWTClaims struct {
	Sub string      `json:"sub"`
	Aud interface{} `json:"aud"`
	Iss string      `json:"iss"`
	Exp int64       `json:"exp"`
	Iat int64       `json:"iat"`
}

// JWTSVIDValidatorConfig configures the validator.
type JWTSVIDValidatorConfig struct {
	JWKSURL          string
	JWKSFile         string
	TrustedDomains   []string
	ExpectedAudience string
	ClockSkew        time.Duration
}

// JWTSVIDValidator validates JWT-SVIDs against a JWKS.
type JWTSVIDValidator struct {
	mu            sync.RWMutex
	cfg           JWTSVIDValidatorConfig
	jwks          *JWKS
	lastFetch     time.Time
	fetchInterval time.Duration
	httpClient    *http.Client
}

// NewJWTSVIDValidator creates a new JWT-SVID validator.
func NewJWTSVIDValidator(cfg JWTSVIDValidatorConfig) *JWTSVIDValidator {
	if cfg.ClockSkew == 0 {
		cfg.ClockSkew = 30 * time.Second
	}
	if cfg.ExpectedAudience == "" {
		cfg.ExpectedAudience = DefaultJWTSVIDAudience
	}
	return &JWTSVIDValidator{
		cfg:           cfg,
		fetchInterval: 5 * time.Minute,
		httpClient:    &http.Client{Timeout: 10 * time.Second},
	}
}

// ValidationResult is the result of JWT-SVID validation.
type ValidationResult struct {
	Valid       bool
	SpiffeID    string
	TrustDomain string
	Issuer      string
	ExpiresAt   time.Time
	Error       string
}

// Validate verifies a raw JWT-SVID token string.
func (v *JWTSVIDValidator) Validate(ctx context.Context, token string) (ValidationResult, error) {
	if err := v.ensureJWKS(ctx); err != nil {
		return ValidationResult{}, fmt.Errorf("load JWKS: %w", err)
	}

	parts := strings.Split(strings.TrimSpace(token), ".")
	if len(parts) != 3 {
		return ValidationResult{Error: "invalid JWT: expected 3 parts"}, nil
	}

	// Parse header
	headerBytes, err := base64URLDecode(parts[0])
	if err != nil {
		return ValidationResult{Error: fmt.Sprintf("decode header: %v", err)}, nil
	}
	var header struct {
		Alg string `json:"alg"`
		Kid string `json:"kid"`
	}
	if err := json.Unmarshal(headerBytes, &header); err != nil {
		return ValidationResult{Error: fmt.Sprintf("parse header: %v", err)}, nil
	}

	// Find matching key
	v.mu.RLock()
	key := v.findKey(header.Kid, header.Alg)
	v.mu.RUnlock()

	if key == nil {
		return ValidationResult{Error: fmt.Sprintf("no key for kid=%s alg=%s", header.Kid, header.Alg)}, nil
	}

	// Verify signature
	signedContent := parts[0] + "." + parts[1]
	if !verifySignature(signedContent, parts[2], key) {
		return ValidationResult{Error: "signature verification failed"}, nil
	}

	// Decode claims
	claimsBytes, err := base64URLDecode(parts[1])
	if err != nil {
		return ValidationResult{Error: fmt.Sprintf("decode claims: %v", err)}, nil
	}
	var claims JWTClaims
	if err := json.Unmarshal(claimsBytes, &claims); err != nil {
		return ValidationResult{Error: fmt.Sprintf("parse claims: %v", err)}, nil
	}

	// Check expiry
	now := time.Now()
	if claims.Exp > 0 && now.After(time.Unix(claims.Exp, 0).Add(v.cfg.ClockSkew)) {
		return ValidationResult{Error: "token expired"}, nil
	}

	// Check audience
	if !v.checkAudience(claims.Aud) {
		return ValidationResult{Error: fmt.Sprintf("audience mismatch: %v", claims.Aud)}, nil
	}

	// Validate SPIFFE subject
	if !strings.HasPrefix(claims.Sub, "spiffe://") {
		return ValidationResult{Error: fmt.Sprintf("not a SPIFFE ID: %s", claims.Sub)}, nil
	}

	trustDomain := extractTrustDomain(claims.Sub)
	if !v.isTrustedDomain(trustDomain) {
		return ValidationResult{Error: fmt.Sprintf("untrusted domain: %s", trustDomain)}, nil
	}

	return ValidationResult{
		Valid:       true,
		SpiffeID:    claims.Sub,
		TrustDomain: trustDomain,
		Issuer:      claims.Iss,
		ExpiresAt:   time.Unix(claims.Exp, 0),
	}, nil
}

func (v *JWTSVIDValidator) ensureJWKS(ctx context.Context) error {
	v.mu.RLock()
	if v.jwks != nil && time.Since(v.lastFetch) < v.fetchInterval {
		v.mu.RUnlock()
		return nil
	}
	v.mu.RUnlock()

	v.mu.Lock()
	defer v.mu.Unlock()

	if v.jwks != nil && time.Since(v.lastFetch) < v.fetchInterval {
		return nil
	}

	if v.cfg.JWKSURL != "" {
		return v.fetchJWKSFromURL(ctx)
	}
	return fmt.Errorf("no JWKS source configured")
}

func (v *JWTSVIDValidator) fetchJWKSFromURL(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, "GET", v.cfg.JWKSURL, nil)
	if err != nil {
		return err
	}
	resp, err := v.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("fetch JWKS: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("JWKS HTTP %d", resp.StatusCode)
	}

	var jwks JWKS
	if err := json.NewDecoder(resp.Body).Decode(&jwks); err != nil {
		return fmt.Errorf("decode JWKS: %w", err)
	}
	v.jwks = &jwks
	v.lastFetch = time.Now()
	return nil
}

func (v *JWTSVIDValidator) findKey(kid, alg string) *JWK {
	if v.jwks == nil {
		return nil
	}
	for i := range v.jwks.Keys {
		k := &v.jwks.Keys[i]
		if kid != "" && k.Kid == kid && k.Alg == alg {
			return k
		}
		if kid == "" && k.Alg == alg {
			return k
		}
	}
	return nil
}

func (v *JWTSVIDValidator) checkAudience(aud interface{}) bool {
	switch a := aud.(type) {
	case string:
		return a == v.cfg.ExpectedAudience
	case []interface{}:
		for _, item := range a {
			if s, ok := item.(string); ok && s == v.cfg.ExpectedAudience {
				return true
			}
		}
	}
	return false
}

func (v *JWTSVIDValidator) isTrustedDomain(domain string) bool {
	if len(v.cfg.TrustedDomains) == 0 {
		return true
	}
	for _, td := range v.cfg.TrustedDomains {
		if td == domain {
			return true
		}
	}
	return false
}

func extractTrustDomain(spiffeID string) string {
	withoutScheme := strings.TrimPrefix(spiffeID, "spiffe://")
	parts := strings.SplitN(withoutScheme, "/", 2)
	if len(parts) > 0 {
		return parts[0]
	}
	return ""
}

func verifySignature(signingInput, signatureB64 string, key *JWK) bool {
	sigBytes, err := base64URLDecode(signatureB64)
	if err != nil {
		return false
	}

	switch key.Alg {
	case "RS256":
		return verifyRS256(signingInput, sigBytes, key)
	case "ES256":
		return verifyES256(signingInput, sigBytes, key)
	default:
		return false
	}
}

func verifyRS256(signingInput string, sigBytes []byte, key *JWK) bool {
	nBytes, err := base64URLDecode(key.N)
	if err != nil {
		return false
	}
	eBytes, err := base64URLDecode(key.E)
	if err != nil {
		return false
	}

	n := new(big.Int).SetBytes(nBytes)
	e := 0
	for _, b := range eBytes {
		e = e<<8 + int(b)
	}

	pubKey := &rsa.PublicKey{N: n, E: e}
	hash := sha256.Sum256([]byte(signingInput))
	return rsa.VerifyPKCS1v15(pubKey, crypto.SHA256, hash[:], sigBytes) == nil
}

func verifyES256(signingInput string, sigBytes []byte, key *JWK) bool {
	xBytes, err := base64URLDecode(key.X)
	if err != nil {
		return false
	}
	yBytes, err := base64URLDecode(key.Y)
	if err != nil {
		return false
	}

	x := new(big.Int).SetBytes(xBytes)
	y := new(big.Int).SetBytes(yBytes)

	pubKey := &ecdsa.PublicKey{
		Curve: elliptic.P256(),
		X:     x,
		Y:     y,
	}

	if len(sigBytes) != 64 {
		return false
	}
	r := new(big.Int).SetBytes(sigBytes[:32])
	s := new(big.Int).SetBytes(sigBytes[32:])

	hash := sha256.Sum256([]byte(signingInput))
	return ecdsa.Verify(pubKey, hash[:], r, s)
}

func base64URLDecode(s string) ([]byte, error) {
	// Add padding if needed
	switch len(s) % 4 {
	case 2:
		s += "=="
	case 3:
		s += "="
	}
	return base64.URLEncoding.DecodeString(s)
}
