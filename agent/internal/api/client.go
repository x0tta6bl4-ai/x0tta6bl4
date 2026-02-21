// Package api implements the HTTP client for the MaaS Control Plane.
// Handles registration, heartbeat, and mesh lifecycle communication.
package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"time"
)

// Client communicates with the MaaS Control Plane API.
type Client struct {
	baseURL    string
	joinToken  string
	apiKey     string // assigned after registration
	meshID     string
	httpClient *http.Client
	logger     *slog.Logger
}

// RegistrationRequest is sent to register a new agent.
type RegistrationRequest struct {
	NodeID   string   `json:"node_id"`
	Token    string   `json:"join_token"`
	Hostname string   `json:"hostname"`
	Arch     string   `json:"arch"`
	OS       string   `json:"os"`
	Version  string   `json:"version"`
	Services []string `json:"services"`
}

// RegistrationResponse is returned from successful registration.
type RegistrationResponse struct {
	MeshID   string `json:"mesh_id"`
	APIKey   string `json:"api_key"`
	NodeName string `json:"node_name"`
	Config   map[string]any `json:"config"`
}

// HeartbeatRequest is the periodic status push.
type HeartbeatRequest struct {
	NodeID       string         `json:"node_id"`
	State        string         `json:"state"`
	PeersTotal   int            `json:"peers_total"`
	PeersHealthy int            `json:"peers_healthy"`
	HealthScore  float64        `json:"health_score"`
	UptimeSec    float64        `json:"uptime_sec"`
	MsgSent      int64          `json:"messages_sent"`
	MsgRecv      int64          `json:"messages_recv"`
	Metrics      map[string]any `json:"metrics,omitempty"`
}

// NewClient creates a new Control Plane API client.
func NewClient(baseURL, joinToken string) *Client {
	return &Client{
		baseURL:   baseURL,
		joinToken: joinToken,
		httpClient: &http.Client{
			Timeout: 15 * time.Second,
		},
		logger: slog.Default().With("component", "api-client"),
	}
}

// Register registers this agent with the Control Plane.
func (c *Client) Register(req RegistrationRequest) (*RegistrationResponse, error) {
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

	c.apiKey = result.APIKey
	c.meshID = result.MeshID

	c.logger.Info("registered with control plane",
		"mesh_id", result.MeshID,
		"node_name", result.NodeName,
	)
	return &result, nil
}

// SendHeartbeat pushes status to the Control Plane.
func (c *Client) SendHeartbeat(hb HeartbeatRequest) error {
	if c.meshID == "" {
		return fmt.Errorf("not registered (no mesh_id)")
	}

	body, err := json.Marshal(hb)
	if err != nil {
		return fmt.Errorf("marshal heartbeat: %w", err)
	}

	url := fmt.Sprintf("%s/api/v1/maas/%s/heartbeat", c.baseURL, c.meshID)
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.apiKey)

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

// GetMeshID returns the assigned mesh ID.
func (c *Client) GetMeshID() string {
	return c.meshID
}

// IsRegistered returns true if the agent is registered.
func (c *Client) IsRegistered() bool {
	return c.apiKey != "" && c.meshID != ""
}
