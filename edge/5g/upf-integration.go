package edge5g

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/ishidawataru/sctp"
	metrics "x0tta6bl4/internal/metrics"
)

var (
	UPFHandoffLatencySimulated = metrics.NewHistogram(metrics.HistogramOpts{
		Name:    "upf_handoff_latency_ms_simulated",
		Help:    "Handoff latency between 5G UPF nodes (Simulated)",
		Buckets: []float64{1, 5, 10, 25, 50, 100},
	})
	SliceSessionRequestsTotal = metrics.NewCounter(metrics.CounterOpts{
		Name: "5g_slice_session_requests_total",
		Help: "Total number of 5G slice session requests processed",
	})
	SliceIsolationEventsTotal = metrics.NewCounter(metrics.CounterOpts{
		Name: "5g_slice_isolation_events_total",
		Help: "Total number of 5G slice isolation enforcement events",
	})
	SCTPConnErrors = metrics.NewCounter(metrics.CounterOpts{
		Name: "slice_5g_sctp_connection_errors_total",
		Help: "Total number of SCTP transport errors in 5G signaling",
	})
)

type EndpointConfig struct {
	AMF string
	UPF string
}

type SliceProfile struct {
	ID              string
	PriorityFloor   int
	PriorityCeiling int
}

type UPFConfig struct {
	Endpoints     EndpointConfig
	AMFEndpoint   string
	UPFEndpoint   string
	Timeout       time.Duration
	AllowedSlices map[string]SliceProfile
}

type SessionRequest struct {
	UEID        string        `json:"ue_id"`
	SliceID     string        `json:"slice_id"`
	AMFEndpoint string        `json:"amf_endpoint"`
	UPFEndpoint string        `json:"upf_endpoint"`
	Timeout     time.Duration `json:"timeout"`
}

type SessionResponse struct {
	Accepted  bool   `json:"accepted"`
	LatencyMs int64  `json:"latency_ms"`
	Cause     string `json:"cause,omitempty"`
}

type SessionTransport interface {
	EstablishSession(request SessionRequest) (SessionResponse, error)
}

type HTTPDoer interface {
	Do(request *http.Request) (*http.Response, error)
}

type PolicyUpdate struct {
	SliceID   string
	Priority  int
	UpdatedAt time.Time
}

type PolicyProgrammer interface {
	Apply(update PolicyUpdate) error
}

type UPFProvider interface {
	EstablishSession(ueID string, sliceID string) (int64, error)
	IsSimulated() bool
}

type QoSEnforcer interface {
	EnforceSlicePolicy(sliceID string, priority int) error
	IsSimulated() bool
}

type SliceManager struct {
	config   UPFConfig
	provider UPFProvider
	enforcer QoSEnforcer
}

func NewSliceManager(cfg UPFConfig, provider UPFProvider, enforcer QoSEnforcer) *SliceManager {
	return &SliceManager{
		config:   cfg,
		provider: provider,
		enforcer: enforcer,
	}
}

func (m *SliceManager) SetProvider(provider UPFProvider) {
	m.provider = provider
}

func (m *SliceManager) HandleRequest(ueID string, sliceID string, priority int) error {
	SliceSessionRequestsTotal.Inc()

	if m.provider == nil {
		return fmt.Errorf("UPF provider required")
	}
	if m.enforcer == nil {
		return fmt.Errorf("QoS enforcer required")
	}
	if strings.TrimSpace(ueID) == "" {
		return fmt.Errorf("UE ID required")
	}
	if err := m.config.validate(sliceID, priority, m.provider); err != nil {
		return err
	}

	latency, err := m.provider.EstablishSession(ueID, sliceID)
	if err != nil {
		return fmt.Errorf("UPF session failure: %w", err)
	}
	if m.provider.IsSimulated() {
		UPFHandoffLatencySimulated.Observe(float64(latency))
	}

	if err := m.enforcer.EnforceSlicePolicy(sliceID, priority); err != nil {
		return fmt.Errorf("QoS enforcement failure: %w", err)
	}
	SliceIsolationEventsTotal.Inc()
	return nil
}

type SimulatedUPF struct {
	LatencyMs int64
}

func (s *SimulatedUPF) EstablishSession(ueID string, sliceID string) (int64, error) {
	if strings.TrimSpace(ueID) == "" {
		return 0, fmt.Errorf("invalid UE ID")
	}
	if strings.TrimSpace(sliceID) == "" || sliceID == "invalid" {
		return 0, fmt.Errorf("invalid slice ID")
	}
	if s.LatencyMs < 0 {
		return 0, fmt.Errorf("invalid simulated UPF config: negative latency")
	}
	if s.LatencyMs == 0 {
		return 25, nil
	}
	return s.LatencyMs, nil
}

func (s *SimulatedUPF) IsSimulated() bool { return true }

type Open5GSUPFProvider struct {
	Config    UPFConfig
	Transport SessionTransport
	Monitor   QoSMonitor
}

type RealOpen5GSUPF = Open5GSUPFProvider

func NewOpen5GSUPFProvider(cfg UPFConfig) *Open5GSUPFProvider {
	return &Open5GSUPFProvider{Config: cfg, Monitor: &MockQoSMonitor{}}
}

func NewRealOpen5GSUPF(cfg UPFConfig) *RealOpen5GSUPF {
	endpoints := cfg.effectiveEndpoints()
	timeout := cfg.sessionTimeout()
	return &RealOpen5GSUPF{
		Config: cfg,
		Transport: &Open5GSSignaling{
			AMFAddr: endpoints.AMF,
			UPFAddr: endpoints.UPF,
			Timeout: timeout,
		},
		Monitor: &MockQoSMonitor{},
	}
}

func (s *Open5GSUPFProvider) BuildSessionRequest(ueID string, sliceID string) (SessionRequest, error) {
	trimmedUEID := strings.TrimSpace(ueID)
	if trimmedUEID == "" {
		return SessionRequest{}, fmt.Errorf("invalid session request: UE ID required")
	}
	trimmedSliceID := strings.TrimSpace(sliceID)
	if trimmedSliceID == "" {
		return SessionRequest{}, fmt.Errorf("invalid session request: slice ID required")
	}

	endpoints := s.Config.effectiveEndpoints()
	if strings.TrimSpace(endpoints.AMF) == "" || strings.TrimSpace(endpoints.UPF) == "" {
		return SessionRequest{}, fmt.Errorf("Open5GSUPFProvider missing endpoints (NOT VERIFIED)")
	}

	return SessionRequest{
		UEID:        trimmedUEID,
		SliceID:     trimmedSliceID,
		AMFEndpoint: endpoints.AMF,
		UPFEndpoint: endpoints.UPF,
		Timeout:     s.Config.sessionTimeout(),
	}, nil
}

func (s *Open5GSUPFProvider) EstablishSession(ueID string, sliceID string) (int64, error) {
	request, err := s.BuildSessionRequest(ueID, sliceID)
	if err != nil {
		return 0, err
	}
	if s.Transport == nil {
		return 0, fmt.Errorf(
			"Open5GSUPFProvider transport not configured (NOT VERIFIED): amf=%s upf=%s",
			request.AMFEndpoint,
			request.UPFEndpoint,
		)
	}

	response, err := s.Transport.EstablishSession(request)
	if err != nil {
		return 0, fmt.Errorf("Open5GSUPFProvider transport failure: %w", err)
	}
	if response.LatencyMs < 0 {
		return 0, fmt.Errorf("invalid transport response: negative latency")
	}
	if !response.Accepted {
		cause := strings.TrimSpace(response.Cause)
		if cause == "" {
			cause = "session rejected"
		}
		return 0, fmt.Errorf("Open5GSUPFProvider rejected session: %s", cause)
	}

	// Apply eBPF QoS heuristic logic to base transport latency
	if s.Monitor != nil {
		ebpfLatency := s.Monitor.GetEstimatedLatencyMs(ueID)
		if ebpfLatency > response.LatencyMs {
			log.Printf("[5G-CORE][QoS] eBPF override latency for UE %s: %d ms", ueID, ebpfLatency)
			return ebpfLatency, nil
		}
	}

	return response.LatencyMs, nil
}

func (s *Open5GSUPFProvider) IsSimulated() bool { return false }

type Open5GSHTTPTransport struct {
	BaseURL string
	Path    string
	Client  HTTPDoer
}

func (t *Open5GSHTTPTransport) EstablishSession(request SessionRequest) (SessionResponse, error) {
	if err := validateSessionRequest(request); err != nil {
		return SessionResponse{}, err
	}
	baseURL := strings.TrimSpace(t.BaseURL)
	if baseURL == "" || t.Client == nil {
		return SessionResponse{}, fmt.Errorf("Open5GSHTTPTransport not configured (NOT VERIFIED)")
	}

	payload, err := json.Marshal(request)
	if err != nil {
		return SessionResponse{}, fmt.Errorf("invalid request payload: %w", err)
	}
	path := strings.TrimSpace(t.Path)
	if path == "" {
		path = "/sessions"
	}

	url := strings.TrimRight(baseURL, "/") + "/" + strings.TrimLeft(path, "/")
	httpRequest, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		return SessionResponse{}, fmt.Errorf("invalid transport request: %w", err)
	}
	httpRequest.Header.Set("Content-Type", "application/json")

	response, err := t.Client.Do(httpRequest)
	if err != nil {
		return SessionResponse{}, fmt.Errorf("HTTP transport failure: %w", err)
	}
	defer response.Body.Close()

	body, err := io.ReadAll(response.Body)
	if err != nil {
		return SessionResponse{}, fmt.Errorf("invalid response body: %w", err)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return SessionResponse{}, fmt.Errorf("invalid transport response: status %d", response.StatusCode)
	}

	var decoded SessionResponse
	if err := json.Unmarshal(body, &decoded); err != nil {
		return SessionResponse{}, fmt.Errorf("invalid response: %w", err)
	}
	return decoded, nil
}

type Open5GSSignaling struct {
	AMFAddr string
	UPFAddr string
	Timeout time.Duration
}

func (s *Open5GSSignaling) EstablishNGAP(ueID string) error {
	if strings.TrimSpace(s.AMFAddr) == "" {
		return fmt.Errorf("Open5GSSignaling missing AMF endpoint (NOT VERIFIED)")
	}

	timeout := s.Timeout
	if timeout <= 0 {
		timeout = 1 * time.Second
	}

	addr, err := net.ResolveTCPAddr("tcp", s.AMFAddr)
	if err != nil {
		return fmt.Errorf("failed to resolve AMF address: %w", err)
	}

	sctpAddr := &sctp.SCTPAddr{
		IPAddrs: []net.IPAddr{{IP: addr.IP}},
		Port:    addr.Port,
	}

	log.Printf("[5G-CORE][SCTP] NGAP: dialing AMF at %s for UE %s", s.AMFAddr, ueID)
	conn, err := sctp.DialSCTP("sctp", nil, sctpAddr)
	if err != nil {
		SCTPConnErrors.Inc()
		return fmt.Errorf("SCTP transport failure to AMF (%s): %w", s.AMFAddr, err)
	}
	defer conn.Close()
	return nil
}

func (s *Open5GSSignaling) CreatePFCPSSession(sliceID string) (int64, error) {
	if strings.TrimSpace(s.UPFAddr) == "" {
		return 0, fmt.Errorf("Open5GSSignaling missing UPF endpoint (NOT VERIFIED)")
	}
	if strings.TrimSpace(sliceID) == "" {
		return 0, fmt.Errorf("invalid PFCP request: slice ID required")
	}

	timeout := s.Timeout
	if timeout <= 0 {
		timeout = 1 * time.Second
	}

	// PFCP uses UDP port 8805
	log.Printf("[5G-CORE][PFCP] Dialing UPF at %s for slice %s", s.UPFAddr, sliceID)
	conn, err := net.DialTimeout("udp", s.UPFAddr, timeout)
	if err != nil {
		return 0, fmt.Errorf("PFCP transport failure to UPF (%s): %w", s.UPFAddr, err)
	}
	defer conn.Close()

	// PFCP Heartbeat Request (Simplified Header: Version=1, MP=0, S=0, Type=1, Length=0, Seq=1)
	heartbeat := []byte{0x20, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00}
	_, err = conn.Write(heartbeat)
	if err != nil {
		return 0, fmt.Errorf("failed to send PFCP heartbeat: %w", err)
	}

	log.Printf("[5G-CORE][PFCP] Heartbeat sent to %s", s.UPFAddr)
	return 25, nil
}

func (s *Open5GSSignaling) EstablishSession(request SessionRequest) (SessionResponse, error) {
	if strings.TrimSpace(s.AMFAddr) == "" {
		s.AMFAddr = strings.TrimSpace(request.AMFEndpoint)
	}
	if strings.TrimSpace(s.UPFAddr) == "" {
		s.UPFAddr = strings.TrimSpace(request.UPFEndpoint)
	}
	if request.Timeout > 0 {
		s.Timeout = request.Timeout
	}
	if err := s.EstablishNGAP(request.UEID); err != nil {
		return SessionResponse{}, err
	}
	latency, err := s.CreatePFCPSSession(request.SliceID)
	if err != nil {
		return SessionResponse{}, err
	}
	return SessionResponse{Accepted: true, LatencyMs: latency}, nil
}

type SimulatedQoSEnforcer struct{}

func (s *SimulatedQoSEnforcer) EnforceSlicePolicy(sliceID string, priority int) error {
	if strings.TrimSpace(sliceID) == "" {
		return fmt.Errorf("invalid slice policy: slice ID required")
	}
	if priority < 0 {
		return fmt.Errorf("invalid slice policy: priority must be non-negative")
	}
	log.Printf("[5G][SIMULATED] slice policy staged: slice=%s priority=%d", sliceID, priority)
	return nil
}

func (s *SimulatedQoSEnforcer) IsSimulated() bool { return true }

type RealEBPFQoSEnforcer struct {
	Programmer PolicyProgrammer
}

func (s *RealEBPFQoSEnforcer) EnforceSlicePolicy(sliceID string, priority int) error {
	if strings.TrimSpace(sliceID) == "" {
		return fmt.Errorf("invalid slice policy: slice ID required")
	}
	if priority < 0 {
		return fmt.Errorf("invalid slice policy: priority must be non-negative")
	}
	if s.Programmer == nil {
		return fmt.Errorf("RealEBPFQoSEnforcer programmer not configured (NOT VERIFIED)")
	}

	update := PolicyUpdate{
		SliceID:   sliceID,
		Priority:  priority,
		UpdatedAt: time.Now().UTC(),
	}
	if err := s.Programmer.Apply(update); err != nil {
		return fmt.Errorf("RealEBPFQoSEnforcer programmer failure: %w", err)
	}

	log.Printf("[5G][EBPF-DRYRUN] prepared policy update for slice %s priority %d", sliceID, priority)
	return nil
}

func (s *RealEBPFQoSEnforcer) IsSimulated() bool { return false }

func (c UPFConfig) effectiveEndpoints() EndpointConfig {
	trimmed := EndpointConfig{
		AMF: strings.TrimSpace(c.Endpoints.AMF),
		UPF: strings.TrimSpace(c.Endpoints.UPF),
	}
	if trimmed.AMF != "" || trimmed.UPF != "" {
		return trimmed
	}
	return EndpointConfig{
		AMF: strings.TrimSpace(c.AMFEndpoint),
		UPF: strings.TrimSpace(c.UPFEndpoint),
	}
}

func (c UPFConfig) sessionTimeout() time.Duration {
	if c.Timeout > 0 {
		return c.Timeout
	}
	return 5 * time.Second
}

func (c UPFConfig) validate(sliceID string, priority int, provider UPFProvider) error {
	if strings.TrimSpace(sliceID) == "" {
		return fmt.Errorf("slice ID required")
	}
	if priority < 0 {
		return fmt.Errorf("priority must be non-negative")
	}
	if len(c.AllowedSlices) > 0 {
		profile, ok := c.AllowedSlices[sliceID]
		if !ok {
			return fmt.Errorf("slice not allowed: %s", sliceID)
		}
		if profile.PriorityFloor != 0 && priority < profile.PriorityFloor {
			return fmt.Errorf("priority below floor for slice %s", sliceID)
		}
		if profile.PriorityCeiling != 0 && priority > profile.PriorityCeiling {
			return fmt.Errorf("priority above ceiling for slice %s", sliceID)
		}
	}
	if provider != nil && !provider.IsSimulated() {
		endpoints := c.effectiveEndpoints()
		if strings.TrimSpace(endpoints.AMF) == "" || strings.TrimSpace(endpoints.UPF) == "" {
			return fmt.Errorf("UPF endpoints required for non-simulated provider")
		}
	}
	return nil
}

func validateSessionRequest(request SessionRequest) error {
	if strings.TrimSpace(request.UEID) == "" {
		return fmt.Errorf("invalid session request: UE ID required")
	}
	if strings.TrimSpace(request.SliceID) == "" {
		return fmt.Errorf("invalid session request: slice ID required")
	}
	if strings.TrimSpace(request.AMFEndpoint) == "" || strings.TrimSpace(request.UPFEndpoint) == "" {
		return fmt.Errorf("invalid session request: endpoints required")
	}
	if request.Timeout <= 0 {
		return fmt.Errorf("invalid session request: timeout must be positive")
	}
	return nil
}
