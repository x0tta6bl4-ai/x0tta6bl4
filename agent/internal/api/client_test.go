package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
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

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v1/maas/agent/register" {
			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(RegistrationResponse{
				MeshID: "mesh-hb", APIKey: "key-hb",
			})
			return
		}

		// Heartbeat endpoint
		if r.Header.Get("X-API-Key") != "key-hb" {
			t.Errorf("X-API-Key = %s", r.Header.Get("X-API-Key"))
		}
		json.NewDecoder(r.Body).Decode(&receivedHB)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(server.URL, "token")
	client.Register(RegistrationRequest{NodeID: "n1"})

	err := client.SendHeartbeat(HeartbeatRequest{
		NodeID:    "n1",
		State:     "running",
		MsgSent:   42,
		UptimeSec: 120.5,
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
}
