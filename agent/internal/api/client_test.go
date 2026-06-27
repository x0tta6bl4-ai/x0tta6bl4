package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestNewClient(t *testing.T) {
	c := NewClient("https://example.com", "token-123")
	if c.baseURL != "https://example.com" {
		t.Errorf("baseURL = %s", c.baseURL)
	}
	if c.joinToken != "token-123" {
		t.Errorf("joinToken = %s", c.joinToken)
	}
	if c.IsRegistered() {
		t.Error("should not be registered initially")
	}
}

func TestRegister_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request
		if r.Method != "POST" {
			t.Errorf("method = %s, want POST", r.Method)
		}
		if r.URL.Path != "/api/v1/maas/agent/register" {
			t.Errorf("path = %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer test-token" {
			t.Errorf("auth = %s", r.Header.Get("Authorization"))
		}
		if r.Header.Get("Content-Type") != "application/json" {
			t.Errorf("content-type = %s", r.Header.Get("Content-Type"))
		}

		// Decode request body
		var req RegistrationRequest
		json.NewDecoder(r.Body).Decode(&req)
		if req.NodeID != "node-1" {
			t.Errorf("node_id = %s", req.NodeID)
		}

		// Return success
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(RegistrationResponse{
			MeshID:   "mesh-abc123",
			APIKey:   "api-key-xyz",
			NodeName: "node-1-prod",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "test-token")
	resp, err := client.Register(RegistrationRequest{
		NodeID:   "node-1",
		Token:    "test-token",
		Hostname: "host-1",
		Arch:     "amd64",
		OS:       "linux",
		Version:  "0.1.0",
		Services: []string{"mesh"},
	})

	if err != nil {
		t.Fatalf("Register: %v", err)
	}
	if resp.MeshID != "mesh-abc123" {
		t.Errorf("MeshID = %s", resp.MeshID)
	}
	if resp.APIKey != "api-key-xyz" {
		t.Errorf("APIKey = %s", resp.APIKey)
	}
	if !client.IsRegistered() {
		t.Error("should be registered after success")
	}
	if client.GetMeshID() != "mesh-abc123" {
		t.Errorf("GetMeshID = %s", client.GetMeshID())
	}
}

func TestRegister_CanonicalMeshNodeEndpoint(t *testing.T) {
	var received map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("method = %s, want POST", r.Method)
		}
		if r.URL.Path != "/api/v1/maas/mesh-abc/nodes/register" {
			t.Errorf("path = %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer test-token" {
			t.Errorf("auth = %s", r.Header.Get("Authorization"))
		}
		if err := json.NewDecoder(r.Body).Decode(&received); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(RegistrationResponse{
			MeshID:                "mesh-abc",
			NodeID:                "node-1",
			NodeRuntimeCredential: "node-runtime-abc",
			Status:                "pending_approval",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL+"/", "test-token")
	resp, err := client.Register(RegistrationRequest{
		MeshID:      "mesh-abc",
		NodeID:      "node-1",
		Token:       "test-token",
		DeviceClass: "edge",
		Hostname:    "host-1",
		Arch:        "amd64",
		OS:          "linux",
		Version:     "0.1.0",
		Services:    []string{"mesh"},
	})

	if err != nil {
		t.Fatalf("Register: %v", err)
	}
	if resp.MeshID != "mesh-abc" {
		t.Errorf("MeshID = %s", resp.MeshID)
	}
	if client.GetMeshID() != "mesh-abc" {
		t.Errorf("GetMeshID = %s", client.GetMeshID())
	}
	if !client.IsRegistered() {
		t.Error("client should keep node_runtime_credential as API key")
	}
	if received["enrollment_token"] != "test-token" {
		t.Errorf("enrollment_token = %v", received["enrollment_token"])
	}
	if received["device_class"] != "edge" {
		t.Errorf("device_class = %v", received["device_class"])
	}
}

func TestRegister_Failure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		w.Write([]byte(`{"detail":"invalid token"}`))
	}))
	defer server.Close()

	client := NewClient(server.URL, "bad-token")
	_, err := client.Register(RegistrationRequest{NodeID: "n1"})
	if err == nil {
		t.Fatal("expected error for 401")
	}
	if client.IsRegistered() {
		t.Error("should not be registered after failure")
	}
}

func TestSendHeartbeat_NotRegistered(t *testing.T) {
	client := NewClient("http://localhost", "token")
	err := client.SendHeartbeat(HeartbeatRequest{NodeID: "n1"})
	if err == nil {
		t.Fatal("expected error when not registered")
	}
}

func TestSendHeartbeat_Success(t *testing.T) {
	var receivedHB HeartbeatRequest
	var heartbeatPath string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v1/maas/mesh-hb/nodes/register" {
			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(RegistrationResponse{
				MeshID: "mesh-hb", NodeID: "n1", APIKey: "key-hb",
			})
			return
		}

		// Heartbeat endpoint
		heartbeatPath = r.URL.Path
		if r.Header.Get("X-API-Key") != "key-hb" {
			t.Errorf("X-API-Key = %s", r.Header.Get("X-API-Key"))
		}
		json.NewDecoder(r.Body).Decode(&receivedHB)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	client.Register(RegistrationRequest{MeshID: "mesh-hb", NodeID: "n1"})

	err := client.SendHeartbeat(HeartbeatRequest{
		NodeID:               "n1",
		State:                "running",
		MsgSent:              42,
		UptimeSec:            120.5,
		DataplaneProbeTarget: "127.0.0.1",
	})

	if err != nil {
		t.Fatalf("SendHeartbeat: %v", err)
	}
	if receivedHB.NodeID != "n1" {
		t.Errorf("received node_id = %s", receivedHB.NodeID)
	}
	if receivedHB.MsgSent != 42 {
		t.Errorf("received messages_sent = %d", receivedHB.MsgSent)
	}
	if heartbeatPath != "/api/v1/maas/mesh-hb/nodes/n1/heartbeat" {
		t.Errorf("heartbeat path = %s", heartbeatPath)
	}
	if receivedHB.Status != "healthy" {
		t.Errorf("received status = %s", receivedHB.Status)
	}
	if receivedHB.DataplaneProbeTarget != "127.0.0.1" {
		t.Errorf("received dataplane_probe_target = %s", receivedHB.DataplaneProbeTarget)
	}
}

func TestSendHeartbeatWithJWTSVID_IncludesSVIDHeader(t *testing.T) {
	var svidHeader string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		svidHeader = r.Header.Get("X-SPIFFE-JWT-SVID")
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	client.meshID = "mesh-hb"
	client.apiKey = "key-hb"

	err := client.SendHeartbeatWithJWTSVID(HeartbeatRequest{NodeID: "n1"}, "jwt-svid-token")
	if err != nil {
		t.Fatalf("SendHeartbeatWithJWTSVID: %v", err)
	}
	if svidHeader != "jwt-svid-token" {
		t.Errorf("X-SPIFFE-JWT-SVID = %s", svidHeader)
	}
}

func TestFetchNodeConfig_RequiresNodeRuntimeCredential(t *testing.T) {
	client := NewClient("https://example.com", "join-token-cfg")

	_, err := client.FetchNodeConfig("mesh-cfg", "node-cfg")
	if err == nil {
		t.Fatal("expected error before node runtime credential is issued")
	}
}

func TestFetchNodeConfig_UsesNodeRuntimeCredential(t *testing.T) {
	var apiKeyHeader string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("method = %s, want GET", r.Method)
		}
		if r.URL.Path != "/api/v1/maas/mesh-cfg/node-config/node-cfg" {
			t.Errorf("path = %s", r.URL.Path)
		}
		apiKeyHeader = r.Header.Get("X-API-Key")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeConfigResponse{
			MeshID:      "mesh-cfg",
			NodeID:      "node-cfg",
			ACLProfile:  "default",
			Policies:    []map[string]any{{"action": "allow"}},
			Peers:       []map[string]any{{"id": "peer-1"}},
			Enforcement: "tag-based",
			GlobalMode:  "zero-trust",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-cfg")
	client.apiKey = "node-runtime-cfg"
	resp, err := client.FetchNodeConfig("mesh-cfg", "node-cfg")
	if err != nil {
		t.Fatalf("FetchNodeConfig: %v", err)
	}
	if apiKeyHeader != "node-runtime-cfg" {
		t.Errorf("X-API-Key = %s", apiKeyHeader)
	}
	if resp.GlobalMode != "zero-trust" {
		t.Errorf("GlobalMode = %s", resp.GlobalMode)
	}
	if len(resp.Policies) != 1 {
		t.Errorf("Policies len = %d", len(resp.Policies))
	}
}

func TestFetchNodeConfigWithJWTSVID_IncludesSVIDHeader(t *testing.T) {
	var svidHeader string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		svidHeader = r.Header.Get("X-SPIFFE-JWT-SVID")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeConfigResponse{
			MeshID:      "mesh-cfg",
			NodeID:      "node-cfg",
			ACLProfile:  "default",
			Policies:    []map[string]any{},
			Peers:       []map[string]any{},
			Enforcement: "tag-based",
			GlobalMode:  "zero-trust",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-cfg")
	client.apiKey = "node-runtime-cfg"
	_, err := client.FetchNodeConfigWithJWTSVID("mesh-cfg", "node-cfg", "jwt-svid-token")
	if err != nil {
		t.Fatalf("FetchNodeConfigWithJWTSVID: %v", err)
	}
	if svidHeader != "jwt-svid-token" {
		t.Errorf("X-SPIFFE-JWT-SVID = %s", svidHeader)
	}
}

func TestRotateNodeRuntimeCredential_RequiresCurrentCredential(t *testing.T) {
	client := NewClient("https://example.com", "join-token-rotate")

	_, err := client.RotateNodeRuntimeCredential("mesh-rotate", "node-rotate", 3600)
	if err == nil {
		t.Fatal("expected error before node runtime credential is issued")
	}
}

func TestRotateNodeRuntimeCredential_UsesCurrentCredentialAndStoresNew(t *testing.T) {
	var apiKeyHeader string
	var received map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("method = %s, want POST", r.Method)
		}
		if r.URL.Path != "/api/v1/maas/mesh-rotate/nodes/node-rotate/runtime-credential/rotate" {
			t.Errorf("path = %s", r.URL.Path)
		}
		apiKeyHeader = r.Header.Get("X-API-Key")
		if err := json.NewDecoder(r.Body).Decode(&received); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeRuntimeCredentialRotateResponse{
			MeshID:                           "mesh-rotate",
			NodeID:                           "node-rotate",
			Status:                           "rotated",
			NodeRuntimeCredential:            "node-runtime-new",
			NodeRuntimeCredentialExpiresAt:   "2026-06-02T00:00:00Z",
			NodeRuntimeCredentialRotatedAt:   "2026-06-01T00:00:00Z",
			RawRuntimeCredentialReturnedOnce: true,
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-rotate")
	client.apiKey = "node-runtime-old"
	resp, err := client.RotateNodeRuntimeCredential("mesh-rotate", "node-rotate", 3600)
	if err != nil {
		t.Fatalf("RotateNodeRuntimeCredential: %v", err)
	}
	if apiKeyHeader != "node-runtime-old" {
		t.Errorf("X-API-Key = %s", apiKeyHeader)
	}
	if received["ttl_seconds"] != float64(3600) {
		t.Errorf("ttl_seconds = %v", received["ttl_seconds"])
	}
	if resp.APIKey != "node-runtime-new" {
		t.Errorf("APIKey = %s", resp.APIKey)
	}
	if client.apiKey != "node-runtime-new" {
		t.Errorf("client apiKey = %s", client.apiKey)
	}
	if client.apiKeyExpiresAt.IsZero() {
		t.Error("client should store runtime credential expiry")
	}
}

func TestRotateNodeRuntimeCredentialWithIdentityProof_IncludesProof(t *testing.T) {
	var received map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := json.NewDecoder(r.Body).Decode(&received); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeRuntimeCredentialRotateResponse{
			MeshID:                         "mesh-proof",
			NodeID:                         "node-proof",
			Status:                         "rotated",
			NodeRuntimeCredential:          "node-runtime-new",
			NodeRuntimeCredentialExpiresAt: "2026-06-02T00:00:00Z",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-rotate")
	client.apiKey = "node-runtime-old"
	_, err := client.RotateNodeRuntimeCredentialWithIdentityProof(
		"mesh-proof",
		"node-proof",
		3600,
		&RuntimeIdentityProof{
			BindingType: "local_spiffe_hint",
			SPIFFEID:    "spiffe://x0tta6bl4.mesh/node/node-proof",
			Nonce:       "stable",
		},
	)
	if err != nil {
		t.Fatalf("RotateNodeRuntimeCredentialWithIdentityProof: %v", err)
	}

	proof, ok := received["identity_proof"].(map[string]any)
	if !ok {
		t.Fatalf("identity_proof missing or wrong type: %#v", received["identity_proof"])
	}
	if proof["binding_type"] != "local_spiffe_hint" {
		t.Errorf("binding_type = %v", proof["binding_type"])
	}
	if proof["spiffe_id"] != "spiffe://x0tta6bl4.mesh/node/node-proof" {
		t.Errorf("spiffe_id = %v", proof["spiffe_id"])
	}
	if proof["nonce"] != "stable" {
		t.Errorf("nonce = %v", proof["nonce"])
	}
}

func TestRotateNodeRuntimeCredentialWithJWTSVID_IncludesSVIDHeader(t *testing.T) {
	var svidHeader string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		svidHeader = r.Header.Get("X-SPIFFE-JWT-SVID")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeRuntimeCredentialRotateResponse{
			MeshID:                         "mesh-proof",
			NodeID:                         "node-proof",
			Status:                         "rotated",
			NodeRuntimeCredential:          "node-runtime-new",
			NodeRuntimeCredentialExpiresAt: "2026-06-02T00:00:00Z",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-rotate")
	client.apiKey = "node-runtime-old"
	_, err := client.RotateNodeRuntimeCredentialWithJWTSVID(
		"mesh-proof",
		"node-proof",
		3600,
		"jwt-svid-token",
	)
	if err != nil {
		t.Fatalf("RotateNodeRuntimeCredentialWithJWTSVID: %v", err)
	}
	if svidHeader != "jwt-svid-token" {
		t.Errorf("X-SPIFFE-JWT-SVID = %s", svidHeader)
	}
}

func TestBindVerifiedRuntimeIdentity_UsesCurrentCredential(t *testing.T) {
	var apiKeyHeader string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("method = %s, want POST", r.Method)
		}
		if r.URL.Path != "/api/v1/maas/mesh-proof/nodes/node-proof/runtime-identity/bind-verified" {
			t.Errorf("path = %s", r.URL.Path)
		}
		apiKeyHeader = r.Header.Get("X-API-Key")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeRuntimeIdentityBindResponse{
			MeshID:                                  "mesh-proof",
			NodeID:                                  "node-proof",
			Status:                                  "bound",
			RuntimeIdentityBindingType:              "verified_spiffe_svid",
			RuntimeIdentityBindingHashPrefix:        "abc123def456",
			RawRuntimeIdentityProofRedacted:         true,
			LiveSPIFFESVIDClaimAllowed:              true,
			TrustedRuntimeIdentityProxyClaimAllowed: true,
			RuntimeIdentityVerificationSource:       "envoy-mtls",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-bind")
	client.apiKey = "node-runtime-current"
	resp, err := client.BindVerifiedRuntimeIdentity("mesh-proof", "node-proof")
	if err != nil {
		t.Fatalf("BindVerifiedRuntimeIdentity: %v", err)
	}
	if apiKeyHeader != "node-runtime-current" {
		t.Errorf("X-API-Key = %s", apiKeyHeader)
	}
	if resp.RuntimeIdentityBindingType != "verified_spiffe_svid" {
		t.Errorf("RuntimeIdentityBindingType = %s", resp.RuntimeIdentityBindingType)
	}
	if !resp.TrustedRuntimeIdentityProxyClaimAllowed {
		t.Error("expected trusted proxy claim to be allowed")
	}
}

func TestBindJWTSVIDRuntimeIdentity_UsesCurrentCredentialAndSVID(t *testing.T) {
	var apiKeyHeader string
	var svidHeader string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("method = %s, want POST", r.Method)
		}
		if r.URL.Path != "/api/v1/maas/mesh-proof/nodes/node-proof/runtime-identity/bind-jwt-svid" {
			t.Errorf("path = %s", r.URL.Path)
		}
		apiKeyHeader = r.Header.Get("X-API-Key")
		svidHeader = r.Header.Get("X-SPIFFE-JWT-SVID")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeRuntimeIdentityBindResponse{
			MeshID:                                 "mesh-proof",
			NodeID:                                 "node-proof",
			Status:                                 "bound",
			RuntimeIdentityBindingType:             "verified_jwt_svid",
			RuntimeIdentityBindingHashPrefix:       "abc123def456",
			RawRuntimeIdentityProofRedacted:        true,
			LiveSPIFFESVIDClaimAllowed:             true,
			APISideJWTSVIDVerificationClaimAllowed: true,
			RuntimeIdentityVerificationSource:      "jwt_svid",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-bind")
	client.apiKey = "node-runtime-current"
	resp, err := client.BindJWTSVIDRuntimeIdentity("mesh-proof", "node-proof", "jwt-svid-token")
	if err != nil {
		t.Fatalf("BindJWTSVIDRuntimeIdentity: %v", err)
	}
	if apiKeyHeader != "node-runtime-current" {
		t.Errorf("X-API-Key = %s", apiKeyHeader)
	}
	if svidHeader != "jwt-svid-token" {
		t.Errorf("X-SPIFFE-JWT-SVID = %s", svidHeader)
	}
	if resp.RuntimeIdentityBindingType != "verified_jwt_svid" {
		t.Errorf("RuntimeIdentityBindingType = %s", resp.RuntimeIdentityBindingType)
	}
	if !resp.APISideJWTSVIDVerificationClaimAllowed {
		t.Error("expected API-side JWT-SVID verification claim to be allowed")
	}
}

func TestRefreshMeasuredAttestationRuntimeIdentity_UsesCurrentCredentialAndRedactedBody(t *testing.T) {
	var apiKeyHeader string
	var received map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("method = %s, want POST", r.Method)
		}
		if r.URL.Path != "/api/v1/maas/mesh-measured/nodes/node-measured/runtime-identity/refresh-measured-attestation" {
			t.Errorf("path = %s", r.URL.Path)
		}
		apiKeyHeader = r.Header.Get("X-API-Key")
		if err := json.NewDecoder(r.Body).Decode(&received); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(NodeRuntimeIdentityBindResponse{
			MeshID:                            "mesh-measured",
			NodeID:                            "node-measured",
			Status:                            "bound",
			RuntimeIdentityBindingType:        "measured_attestation",
			RuntimeIdentityBindingHashPrefix:  "abc123def456",
			RawRuntimeIdentityProofRedacted:   true,
			RuntimeIdentityVerificationSource: "tee:sgx",
		})
	}))
	defer server.Close()

	client := NewClient(server.URL, "join-token-bind")
	client.apiKey = "node-runtime-current"
	resp, err := client.RefreshMeasuredAttestationRuntimeIdentity(
		"mesh-measured",
		"node-measured",
		&MeasuredAttestationData{
			Provider:      "sgx",
			ReportDataB64: "cmVwb3J0",
			QuoteB64:      "cXVvdGU=",
			SignatureB64:  "c2ln",
		},
	)
	if err != nil {
		t.Fatalf("RefreshMeasuredAttestationRuntimeIdentity: %v", err)
	}
	if apiKeyHeader != "node-runtime-current" {
		t.Errorf("X-API-Key = %s", apiKeyHeader)
	}
	attestation, ok := received["attestation_data"].(map[string]any)
	if !ok {
		t.Fatalf("attestation_data missing or wrong type: %#v", received["attestation_data"])
	}
	if attestation["provider"] != "sgx" {
		t.Errorf("provider = %v", attestation["provider"])
	}
	if attestation["report_data_b64"] != "cmVwb3J0" {
		t.Errorf("report_data_b64 = %v", attestation["report_data_b64"])
	}
	if resp.RuntimeIdentityBindingType != "measured_attestation" {
		t.Errorf("RuntimeIdentityBindingType = %s", resp.RuntimeIdentityBindingType)
	}
	if !resp.RawRuntimeIdentityProofRedacted {
		t.Error("expected raw runtime identity proof to be redacted")
	}
}

func TestShouldRotateNodeRuntimeCredential(t *testing.T) {
	client := NewClient("https://example.com", "join-token")
	client.apiKey = "node-runtime"
	client.apiKeyExpiresAt = time.Now().Add(2 * time.Minute)

	if !client.ShouldRotateNodeRuntimeCredential(5 * time.Minute) {
		t.Fatal("expected credential inside rotation window")
	}

	client.apiKeyExpiresAt = time.Now().Add(2 * time.Hour)
	if client.ShouldRotateNodeRuntimeCredential(5 * time.Minute) {
		t.Fatal("did not expect credential outside rotation window")
	}
}
