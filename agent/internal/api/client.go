// Package api implements the HTTP client for the MaaS Control Plane.
// Handles registration, heartbeat, and mesh lifecycle communication.
package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Client communicates with the MaaS Control Plane API.
type Client struct {
	baseURL         string
	joinToken       string
	apiKey          string // assigned after registration
	apiKeyExpiresAt time.Time
	meshID          string
	httpClient      *http.Client
	logger          *slog.Logger
}

// RegistrationRequest is sent to register a new agent.
type RegistrationRequest struct {
	NodeID      string   `json:"node_id"`
	MeshID      string   `json:"mesh_id,omitempty"`
	Token       string   `json:"join_token"`
	DeviceClass string   `json:"device_class,omitempty"`
	Hostname    string   `json:"hostname"`
	Arch        string   `json:"arch"`
	OS          string   `json:"os"`
	Version     string   `json:"version"`
	Services    []string `json:"services"`
}

// RegistrationResponse is returned from successful registration.
type RegistrationResponse struct {
	MeshID                         string         `json:"mesh_id"`
	NodeID                         string         `json:"node_id"`
	APIKey                         string         `json:"api_key"`
	NodeRuntimeCredential          string         `json:"node_runtime_credential"`
	NodeRuntimeCredentialExpiresAt string         `json:"node_runtime_credential_expires_at"`
	NodeName                       string         `json:"node_name"`
	Status                         string         `json:"status"`
	Message                        string         `json:"message"`
	Config                         map[string]any `json:"config"`
}

// HeartbeatRequest is the periodic status push.
type HeartbeatRequest struct {
	NodeID               string         `json:"node_id"`
	Status               string         `json:"status,omitempty"`
	State                string         `json:"state"`
	PeersTotal           int            `json:"peers_total"`
	PeersHealthy         int            `json:"peers_healthy"`
	HealthScore          float64        `json:"health_score"`
	UptimeSec            float64        `json:"uptime_sec"`
	MsgSent              int64          `json:"messages_sent"`
	MsgRecv              int64          `json:"messages_recv"`
	DataplaneProbeTarget string         `json:"dataplane_probe_target,omitempty"`
	Metrics              map[string]any `json:"metrics,omitempty"`
}

// NodeConfigResponse is returned by the MaaS node-config endpoint.
type NodeConfigResponse struct {
	MeshID      string           `json:"mesh_id"`
	NodeID      string           `json:"node_id"`
	ACLProfile  string           `json:"acl_profile"`
	Policies    []map[string]any `json:"policies"`
	Peers       []map[string]any `json:"peers"`
	Enforcement string           `json:"enforcement"`
	GlobalMode  string           `json:"global_mode"`
}

// NodeRuntimeCredentialRotateResponse is returned after credential rotation.
type NodeRuntimeCredentialRotateResponse struct {
	MeshID                           string `json:"mesh_id"`
	NodeID                           string `json:"node_id"`
	Status                           string `json:"status"`
	APIKey                           string `json:"api_key"`
	NodeRuntimeCredential            string `json:"node_runtime_credential"`
	NodeRuntimeCredentialExpiresAt   string `json:"node_runtime_credential_expires_at"`
	NodeRuntimeCredentialRotatedAt   string `json:"node_runtime_credential_rotated_at"`
	RawRuntimeCredentialReturnedOnce bool   `json:"raw_runtime_credential_returned_once"`
}

// NodeRuntimeIdentityBindResponse is returned after trusted identity binding.
type NodeRuntimeIdentityBindResponse struct {
	MeshID                                  string `json:"mesh_id"`
	NodeID                                  string `json:"node_id"`
	Status                                  string `json:"status"`
	RuntimeIdentityBindingType              string `json:"runtime_identity_binding_type"`
	RuntimeIdentityBindingHashPrefix        string `json:"runtime_identity_binding_hash_prefix"`
	RuntimeIdentityBoundAt                  string `json:"runtime_identity_bound_at"`
	RuntimeIdentityLastVerifiedAt           string `json:"runtime_identity_last_verified_at"`
	RawRuntimeIdentityProofRedacted         bool   `json:"raw_runtime_identity_proof_redacted"`
	LiveSPIFFESVIDClaimAllowed              bool   `json:"live_spiffe_svid_claim_allowed"`
	TrustedRuntimeIdentityProxyClaimAllowed bool   `json:"trusted_runtime_identity_proxy_claim_allowed"`
	APISideJWTSVIDVerificationClaimAllowed  bool   `json:"api_side_jwt_svid_verification_claim_allowed"`
	RuntimeIdentityVerificationSource       string `json:"runtime_identity_verification_source"`
	ProductionTrustFinalityClaimAllowed     bool   `json:"production_trust_finality_claim_allowed"`
}

// MeasuredAttestationData is redacted by the API after verification.
type MeasuredAttestationData struct {
	Provider      string `json:"provider,omitempty"`
	ReportData    string `json:"report_data,omitempty"`
	ReportDataB64 string `json:"report_data_b64,omitempty"`
	Quote         string `json:"quote,omitempty"`
	QuoteB64      string `json:"quote_b64,omitempty"`
	Signature     string `json:"signature,omitempty"`
	SignatureB64  string `json:"signature_b64,omitempty"`
}

func (d *MeasuredAttestationData) IsConfigured() bool {
	if d == nil {
		return false
	}
	return strings.TrimSpace(d.ReportData) != "" ||
		strings.TrimSpace(d.ReportDataB64) != "" ||
		strings.TrimSpace(d.Quote) != "" ||
		strings.TrimSpace(d.QuoteB64) != "" ||
		strings.TrimSpace(d.Signature) != "" ||
		strings.TrimSpace(d.SignatureB64) != ""
}

func (d *MeasuredAttestationData) isConfigured() bool {
	return d.IsConfigured()
}

// RuntimeIdentityProof is optional hash-bound local identity evidence for rotation.
type RuntimeIdentityProof struct {
	BindingType       string `json:"binding_type"`
	SPIFFEID          string `json:"spiffe_id,omitempty"`
	AttestationDigest string `json:"attestation_digest,omitempty"`
	Nonce             string `json:"nonce,omitempty"`
}

func (p *RuntimeIdentityProof) isConfigured() bool {
	return p != nil && strings.TrimSpace(p.BindingType) != ""
}

// NewClient creates a new Control Plane API client.
func NewClient(baseURL, joinToken string) *Client {
	return &Client{
		baseURL:   strings.TrimRight(baseURL, "/"),
		joinToken: joinToken,
		httpClient: &http.Client{
			Timeout: 15 * time.Second,
		},
		logger: slog.Default().With("component", "api-client"),
	}
}

// Register registers this agent with the Control Plane.
func (c *Client) Register(req RegistrationRequest) (*RegistrationResponse, error) {
	if req.MeshID != "" {
		return c.registerNode(req)
	}
	return c.registerLegacyAgent(req)
}

func (c *Client) registerNode(req RegistrationRequest) (*RegistrationResponse, error) {
	enrollmentToken := req.Token
	if enrollmentToken == "" {
		enrollmentToken = c.joinToken
	}
	deviceClass := req.DeviceClass
	if deviceClass == "" {
		deviceClass = "edge"
	}

	body, err := json.Marshal(map[string]any{
		"node_id":          req.NodeID,
		"enrollment_token": enrollmentToken,
		"device_class":     deviceClass,
		"metadata": map[string]any{
			"hostname": req.Hostname,
			"arch":     req.Arch,
			"os":       req.OS,
			"version":  req.Version,
			"services": req.Services,
		},
	})
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/nodes/register",
		c.baseURL,
		url.PathEscape(req.MeshID),
	)
	httpReq, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+enrollmentToken)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("registration failed (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var result RegistrationResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	if result.MeshID == "" {
		result.MeshID = req.MeshID
	}
	if result.NodeID == "" {
		result.NodeID = req.NodeID
	}
	if result.NodeName == "" {
		result.NodeName = result.NodeID
	}
	if result.APIKey == "" {
		result.APIKey = result.NodeRuntimeCredential
	}

	c.SetNodeRuntimeCredential(result.APIKey, result.NodeRuntimeCredentialExpiresAt)
	c.meshID = result.MeshID
	c.logger.Info("registered with control plane",
		"mesh_id", result.MeshID,
		"node_name", result.NodeName,
		"status", result.Status,
	)
	return &result, nil
}

func (c *Client) registerLegacyAgent(req RegistrationRequest) (*RegistrationResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	url := fmt.Sprintf("%s/api/v1/maas/agent/register", c.baseURL)
	httpReq, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+c.joinToken)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("registration failed (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var result RegistrationResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	c.SetNodeRuntimeCredential(result.APIKey, result.NodeRuntimeCredentialExpiresAt)
	c.meshID = result.MeshID

	c.logger.Info("registered with control plane",
		"mesh_id", result.MeshID,
		"node_name", result.NodeName,
	)
	return &result, nil
}

// SendHeartbeat pushes status to the Control Plane.
func (c *Client) SendHeartbeat(hb HeartbeatRequest) error {
	return c.SendHeartbeatWithJWTSVID(hb, "")
}

// SendHeartbeatWithJWTSVID pushes status with an optional live JWT-SVID.
func (c *Client) SendHeartbeatWithJWTSVID(hb HeartbeatRequest, jwtSVID string) error {
	if c.meshID == "" {
		return fmt.Errorf("not registered (no mesh_id)")
	}
	if hb.NodeID == "" {
		return fmt.Errorf("heartbeat missing node_id")
	}
	if hb.Status == "" {
		hb.Status = normalizeHeartbeatStatus(hb.State)
	}

	body, err := json.Marshal(hb)
	if err != nil {
		return fmt.Errorf("marshal heartbeat: %w", err)
	}

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/nodes/%s/heartbeat",
		c.baseURL,
		url.PathEscape(c.meshID),
		url.PathEscape(hb.NodeID),
	)
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.apiKey)
	if strings.TrimSpace(jwtSVID) != "" {
		req.Header.Set("X-SPIFFE-JWT-SVID", strings.TrimSpace(jwtSVID))
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("send heartbeat: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("heartbeat failed (HTTP %d)", resp.StatusCode)
	}

	return nil
}

// SendHealingAlert posts a self-healing event to the control plane.
func (c *Client) SendHealingAlert(ctx context.Context, nodeID, diagnosis, action string) error {
	if c.meshID == "" {
		return fmt.Errorf("healing alert requires registered mesh")
	}
	if nodeID == "" {
		return fmt.Errorf("healing alert requires node_id")
	}

	body, _ := json.Marshal(map[string]string{
		"node_id":   nodeID,
		"diagnosis": diagnosis,
		"action":    action,
	})

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/nodes/%s/healing-alert",
		c.baseURL,
		url.PathEscape(c.meshID),
		url.PathEscape(nodeID),
	)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create healing alert request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("send healing alert: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		return fmt.Errorf("healing alert failed (HTTP %d)", resp.StatusCode)
	}
	return nil
}

// FetchNodeConfig fetches the approved agent's zero-trust peer/policy config.
func (c *Client) FetchNodeConfig(meshID, nodeID string) (*NodeConfigResponse, error) {
	return c.FetchNodeConfigWithJWTSVID(meshID, nodeID, "")
}

// FetchNodeConfigWithJWTSVID fetches node config with an optional live JWT-SVID.
func (c *Client) FetchNodeConfigWithJWTSVID(meshID, nodeID string, jwtSVID string) (*NodeConfigResponse, error) {
	if c.apiKey == "" {
		return nil, fmt.Errorf("node config requires node runtime credential")
	}
	if meshID == "" {
		meshID = c.meshID
	}
	if meshID == "" {
		return nil, fmt.Errorf("node config missing mesh_id")
	}
	if nodeID == "" {
		return nil, fmt.Errorf("node config missing node_id")
	}

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/node-config/%s",
		c.baseURL,
		url.PathEscape(meshID),
		url.PathEscape(nodeID),
	)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create node config request: %w", err)
	}
	req.Header.Set("X-API-Key", c.apiKey)
	if strings.TrimSpace(jwtSVID) != "" {
		req.Header.Set("X-SPIFFE-JWT-SVID", strings.TrimSpace(jwtSVID))
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("send node config request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("node config failed (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var result NodeConfigResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode node config response: %w", err)
	}
	return &result, nil
}

// RotateNodeRuntimeCredential rotates this node's scoped runtime credential.
func (c *Client) RotateNodeRuntimeCredential(meshID, nodeID string, ttlSeconds int) (*NodeRuntimeCredentialRotateResponse, error) {
	return c.RotateNodeRuntimeCredentialWithIdentityProof(meshID, nodeID, ttlSeconds, nil)
}

// RotateNodeRuntimeCredentialWithIdentityProof rotates the credential with optional identity proof.
func (c *Client) RotateNodeRuntimeCredentialWithIdentityProof(meshID, nodeID string, ttlSeconds int, proof *RuntimeIdentityProof) (*NodeRuntimeCredentialRotateResponse, error) {
	return c.rotateNodeRuntimeCredential(meshID, nodeID, ttlSeconds, proof, "")
}

// RotateNodeRuntimeCredentialWithJWTSVID rotates the credential with a live JWT-SVID.
func (c *Client) RotateNodeRuntimeCredentialWithJWTSVID(meshID, nodeID string, ttlSeconds int, jwtSVID string) (*NodeRuntimeCredentialRotateResponse, error) {
	if strings.TrimSpace(jwtSVID) == "" {
		return nil, fmt.Errorf("node credential rotation requires JWT-SVID")
	}
	return c.rotateNodeRuntimeCredential(meshID, nodeID, ttlSeconds, nil, jwtSVID)
}

func (c *Client) rotateNodeRuntimeCredential(meshID, nodeID string, ttlSeconds int, proof *RuntimeIdentityProof, jwtSVID string) (*NodeRuntimeCredentialRotateResponse, error) {
	if c.apiKey == "" {
		return nil, fmt.Errorf("node credential rotation requires current node runtime credential")
	}
	if meshID == "" {
		meshID = c.meshID
	}
	if meshID == "" {
		return nil, fmt.Errorf("node credential rotation missing mesh_id")
	}
	if nodeID == "" {
		return nil, fmt.Errorf("node credential rotation missing node_id")
	}
	if ttlSeconds <= 0 {
		ttlSeconds = 86400
	}

	payload := map[string]any{"ttl_seconds": ttlSeconds}
	if proof.isConfigured() {
		payload["identity_proof"] = proof
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal node credential rotation request: %w", err)
	}

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/nodes/%s/runtime-credential/rotate",
		c.baseURL,
		url.PathEscape(meshID),
		url.PathEscape(nodeID),
	)
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create node credential rotation request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.apiKey)
	if strings.TrimSpace(jwtSVID) != "" {
		req.Header.Set("X-SPIFFE-JWT-SVID", strings.TrimSpace(jwtSVID))
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("send node credential rotation request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("node credential rotation failed (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var result NodeRuntimeCredentialRotateResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode node credential rotation response: %w", err)
	}
	if result.APIKey == "" {
		result.APIKey = result.NodeRuntimeCredential
	}
	if result.APIKey == "" {
		return nil, fmt.Errorf("node credential rotation response missing credential")
	}
	c.SetNodeRuntimeCredential(result.APIKey, result.NodeRuntimeCredentialExpiresAt)
	return &result, nil
}

// BindVerifiedRuntimeIdentity asks the control plane to bind proxy-verified SPIFFE identity.
func (c *Client) BindVerifiedRuntimeIdentity(meshID, nodeID string) (*NodeRuntimeIdentityBindResponse, error) {
	if c.apiKey == "" {
		return nil, fmt.Errorf("verified runtime identity binding requires current node runtime credential")
	}
	if meshID == "" {
		meshID = c.meshID
	}
	if meshID == "" {
		return nil, fmt.Errorf("verified runtime identity binding missing mesh_id")
	}
	if nodeID == "" {
		return nil, fmt.Errorf("verified runtime identity binding missing node_id")
	}

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/nodes/%s/runtime-identity/bind-verified",
		c.baseURL,
		url.PathEscape(meshID),
		url.PathEscape(nodeID),
	)
	req, err := http.NewRequest("POST", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create verified runtime identity binding request: %w", err)
	}
	req.Header.Set("X-API-Key", c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("send verified runtime identity binding request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("verified runtime identity binding failed (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var result NodeRuntimeIdentityBindResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode verified runtime identity binding response: %w", err)
	}
	return &result, nil
}

// BindJWTSVIDRuntimeIdentity asks the control plane to bind API-verified JWT-SVID identity.
func (c *Client) BindJWTSVIDRuntimeIdentity(meshID, nodeID string, jwtSVID string) (*NodeRuntimeIdentityBindResponse, error) {
	if c.apiKey == "" {
		return nil, fmt.Errorf("JWT-SVID runtime identity binding requires current node runtime credential")
	}
	if strings.TrimSpace(jwtSVID) == "" {
		return nil, fmt.Errorf("JWT-SVID runtime identity binding requires JWT-SVID")
	}
	if meshID == "" {
		meshID = c.meshID
	}
	if meshID == "" {
		return nil, fmt.Errorf("JWT-SVID runtime identity binding missing mesh_id")
	}
	if nodeID == "" {
		return nil, fmt.Errorf("JWT-SVID runtime identity binding missing node_id")
	}

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/nodes/%s/runtime-identity/bind-jwt-svid",
		c.baseURL,
		url.PathEscape(meshID),
		url.PathEscape(nodeID),
	)
	req, err := http.NewRequest("POST", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create JWT-SVID runtime identity binding request: %w", err)
	}
	req.Header.Set("X-API-Key", c.apiKey)
	req.Header.Set("X-SPIFFE-JWT-SVID", strings.TrimSpace(jwtSVID))

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("send JWT-SVID runtime identity binding request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("JWT-SVID runtime identity binding failed (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var result NodeRuntimeIdentityBindResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode JWT-SVID runtime identity binding response: %w", err)
	}
	return &result, nil
}

// RefreshMeasuredAttestationRuntimeIdentity refreshes a measured-attestation binding.
func (c *Client) RefreshMeasuredAttestationRuntimeIdentity(meshID, nodeID string, attestation *MeasuredAttestationData) (*NodeRuntimeIdentityBindResponse, error) {
	if c.apiKey == "" {
		return nil, fmt.Errorf("measured attestation refresh requires current node runtime credential")
	}
	if !attestation.isConfigured() {
		return nil, fmt.Errorf("measured attestation refresh requires attestation data")
	}
	if meshID == "" {
		meshID = c.meshID
	}
	if meshID == "" {
		return nil, fmt.Errorf("measured attestation refresh missing mesh_id")
	}
	if nodeID == "" {
		return nil, fmt.Errorf("measured attestation refresh missing node_id")
	}

	body, err := json.Marshal(map[string]any{"attestation_data": attestation})
	if err != nil {
		return nil, fmt.Errorf("marshal measured attestation refresh request: %w", err)
	}

	url := fmt.Sprintf(
		"%s/api/v1/maas/%s/nodes/%s/runtime-identity/refresh-measured-attestation",
		c.baseURL,
		url.PathEscape(meshID),
		url.PathEscape(nodeID),
	)
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create measured attestation refresh request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.apiKey)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("send measured attestation refresh request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("measured attestation refresh failed (HTTP %d): %s", resp.StatusCode, string(bodyBytes))
	}

	var result NodeRuntimeIdentityBindResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode measured attestation refresh response: %w", err)
	}
	return &result, nil
}

func (c *Client) SetNodeRuntimeCredential(credential, expiresAt string) {
	c.apiKey = credential
	c.apiKeyExpiresAt = parseAPITime(expiresAt)
}

// SetMeshID sets the mesh ID directly.
func (c *Client) SetMeshID(meshID string) {
	c.meshID = meshID
}

func parseAPITime(value string) time.Time {
	normalized := strings.TrimSpace(value)
	if normalized == "" {
		return time.Time{}
	}
	for _, layout := range []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
	} {
		parsed, err := time.Parse(layout, normalized)
		if err == nil {
			return parsed
		}
	}
	return time.Time{}
}

// ShouldRotateNodeRuntimeCredential reports whether the credential is close to expiry.
func (c *Client) ShouldRotateNodeRuntimeCredential(window time.Duration) bool {
	if c.apiKey == "" || c.apiKeyExpiresAt.IsZero() {
		return false
	}
	if window < 0 {
		window = 0
	}
	return time.Now().Add(window).After(c.apiKeyExpiresAt)
}

func normalizeHeartbeatStatus(state string) string {
	switch strings.ToLower(strings.TrimSpace(state)) {
	case "", "healthy", "online", "ready", "running", "started":
		return "healthy"
	case "degraded", "warning", "warn":
		return "degraded"
	case "unhealthy", "failed", "failure", "offline", "error", "stopped":
		return "unhealthy"
	default:
		return "healthy"
	}
}

// GetMeshID returns the assigned mesh ID.
func (c *Client) GetMeshID() string {
	return c.meshID
}

// IsRegistered returns true if the agent is registered.
func (c *Client) IsRegistered() bool {
	return c.apiKey != "" && c.meshID != ""
}
