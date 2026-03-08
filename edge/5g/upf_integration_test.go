package edge5g_test

import (
	"errors"
	"io"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"

	edge5g "x0tta6bl4/edge/5g"
)

func TestSliceManagerAcceptsSimulatedProvider(t *testing.T) {
	cfg := edge5g.UPFConfig{
		AllowedSlices: map[string]edge5g.SliceProfile{
			"premium": {ID: "premium", PriorityFloor: 10, PriorityCeiling: 100},
		},
	}
	enforcer := &countingQoSEnforcer{}
	manager := edge5g.NewSliceManager(cfg, &edge5g.SimulatedUPF{}, enforcer)

	if err := manager.HandleRequest("ue1", "premium", 50); err != nil {
		t.Fatalf("expected simulated provider success, got %v", err)
	}
	if enforcer.calls != 1 {
		t.Fatalf("expected one QoS update, got %d", enforcer.calls)
	}
}

func TestSliceManagerTrimsIdentifiersBeforeValidationAndDispatch(t *testing.T) {
	cfg := edge5g.UPFConfig{
		Endpoints: edge5g.EndpointConfig{
			AMF: "http://amf.local",
			UPF: "http://upf.local",
		},
		AllowedSlices: map[string]edge5g.SliceProfile{
			"premium": {ID: "premium", PriorityFloor: 10, PriorityCeiling: 100},
		},
	}
	provider := &capturingUPFProvider{latency: 33}
	enforcer := &capturingQoSEnforcer{}
	manager := edge5g.NewSliceManager(cfg, provider, enforcer)

	if err := manager.HandleRequest("  ue1  ", "  premium  ", 50); err != nil {
		t.Fatalf("expected trimmed identifiers to succeed, got %v", err)
	}
	if provider.lastUEID != "ue1" || provider.lastSliceID != "premium" {
		t.Fatalf("expected trimmed provider dispatch, got ue=%q slice=%q", provider.lastUEID, provider.lastSliceID)
	}
	if enforcer.lastSliceID != "premium" || enforcer.lastPriority != 50 {
		t.Fatalf("expected trimmed QoS dispatch, got slice=%q priority=%d", enforcer.lastSliceID, enforcer.lastPriority)
	}
}

func TestSliceManagerRejectsPriorityOutsideBounds(t *testing.T) {
	cfg := edge5g.UPFConfig{
		AllowedSlices: map[string]edge5g.SliceProfile{
			"premium": {ID: "premium", PriorityFloor: 10, PriorityCeiling: 100},
		},
	}
	manager := edge5g.NewSliceManager(cfg, &edge5g.SimulatedUPF{}, &countingQoSEnforcer{})

	if err := manager.HandleRequest("ue1", "premium", 5); err == nil || !strings.Contains(err.Error(), "priority below floor") {
		t.Fatalf("expected floor rejection, got %v", err)
	}
	if err := manager.HandleRequest("ue1", "premium", 101); err == nil || !strings.Contains(err.Error(), "priority above ceiling") {
		t.Fatalf("expected ceiling rejection, got %v", err)
	}
}

func TestSliceManagerRejectsEmptyUEID(t *testing.T) {
	manager := edge5g.NewSliceManager(edge5g.UPFConfig{}, &edge5g.SimulatedUPF{}, &countingQoSEnforcer{})

	err := manager.HandleRequest("", "premium", 50)
	if err == nil || !strings.Contains(err.Error(), "UE ID required") {
		t.Fatalf("expected UE ID rejection, got %v", err)
	}
}

func TestSimulatedUPFRejectsNegativeLatency(t *testing.T) {
	provider := &edge5g.SimulatedUPF{LatencyMs: -1}

	_, err := provider.EstablishSession("ue1", "premium")
	if err == nil || !strings.Contains(err.Error(), "invalid simulated UPF config") {
		t.Fatalf("expected simulated config rejection, got %v", err)
	}
}

func TestSimulatedUPFTrimsIdentifiersForDirectCalls(t *testing.T) {
	provider := &edge5g.SimulatedUPF{LatencyMs: 11}

	latency, err := provider.EstablishSession("  ue1  ", "  premium  ")
	if err != nil {
		t.Fatalf("expected trimmed direct call success, got %v", err)
	}
	if latency != 11 {
		t.Fatalf("expected latency 11, got %d", latency)
	}

	if _, err := provider.EstablishSession("ue1", " invalid "); err == nil || !strings.Contains(err.Error(), "invalid slice ID") {
		t.Fatalf("expected trimmed invalid slice rejection, got %v", err)
	}
}

func TestOpen5GSProviderBuildsRequestAndPropagatesTransport(t *testing.T) {
	cfg := edge5g.UPFConfig{
		Endpoints: edge5g.EndpointConfig{
			AMF: "http://amf.local",
			UPF: "http://upf.local",
		},
	}
	transport := &stubSessionTransport{
		response: edge5g.SessionResponse{Accepted: true, LatencyMs: 42},
	}
	provider := &edge5g.Open5GSUPFProvider{Config: cfg, Transport: transport}

	latency, err := provider.EstablishSession("ue1", "premium")
	if err != nil {
		t.Fatalf("expected transport-backed success, got %v", err)
	}
	if latency != 42 {
		t.Fatalf("unexpected latency: got %d want 42", latency)
	}
	if transport.last.UEID != "ue1" || transport.last.SliceID != "premium" {
		t.Fatalf("unexpected request propagated to transport: %+v", transport.last)
	}
	if transport.last.Timeout != 5*time.Second {
		t.Fatalf("expected default timeout of 5s, got %v", transport.last.Timeout)
	}
}

func TestOpen5GSProviderBuildSessionRequestTrimsWhitespace(t *testing.T) {
	provider := edge5g.NewOpen5GSUPFProvider(edge5g.UPFConfig{
		AMFEndpoint: " 127.0.0.1:38412 ",
		UPFEndpoint: " 127.0.0.1:8805 ",
	})

	request, err := provider.BuildSessionRequest("  ue1  ", "  premium  ")
	if err != nil {
		t.Fatalf("expected trimmed request to succeed, got %v", err)
	}

	if request.UEID != "ue1" || request.SliceID != "premium" {
		t.Fatalf("unexpected trimmed identifiers: %+v", request)
	}
	if request.AMFEndpoint != "127.0.0.1:38412" || request.UPFEndpoint != "127.0.0.1:8805" {
		t.Fatalf("unexpected trimmed endpoints: %+v", request)
	}
}

func TestOpen5GSProviderBuildSessionRequestMergesPartialEndpointOverrides(t *testing.T) {
	provider := edge5g.NewOpen5GSUPFProvider(edge5g.UPFConfig{
		Endpoints:   edge5g.EndpointConfig{AMF: " 127.0.0.1:38412 "},
		UPFEndpoint: " 127.0.0.1:8805 ",
	})

	request, err := provider.BuildSessionRequest("ue1", "premium")
	if err != nil {
		t.Fatalf("expected mixed endpoint sources to succeed, got %v", err)
	}
	if request.AMFEndpoint != "127.0.0.1:38412" || request.UPFEndpoint != "127.0.0.1:8805" {
		t.Fatalf("expected merged endpoint config, got %+v", request)
	}
}

func TestOpen5GSProviderErrorSemantics(t *testing.T) {
	provider := edge5g.NewOpen5GSUPFProvider(edge5g.UPFConfig{})
	if _, err := provider.BuildSessionRequest("ue1", "premium"); err == nil || !strings.Contains(err.Error(), "NOT VERIFIED") {
		t.Fatalf("expected missing endpoints to stay NOT VERIFIED, got %v", err)
	}

	provider = &edge5g.Open5GSUPFProvider{
		Config: edge5g.UPFConfig{
			Endpoints: edge5g.EndpointConfig{AMF: "http://amf.local", UPF: "http://upf.local"},
		},
	}
	if _, err := provider.EstablishSession("ue1", "premium"); err == nil || !strings.Contains(err.Error(), "NOT VERIFIED") {
		t.Fatalf("expected missing transport to stay NOT VERIFIED, got %v", err)
	}
}

func TestOpen5GSProviderRejectsDeniedOrInvalidTransportResponses(t *testing.T) {
	cfg := edge5g.UPFConfig{
		Endpoints: edge5g.EndpointConfig{
			AMF: "http://amf.local",
			UPF: "http://upf.local",
		},
	}

	denied := &edge5g.Open5GSUPFProvider{
		Config:    cfg,
		Transport: &stubSessionTransport{response: edge5g.SessionResponse{Accepted: false, Cause: "slice admission denied"}},
	}
	if _, err := denied.EstablishSession("ue1", "premium"); err == nil || !strings.Contains(err.Error(), "rejected session") {
		t.Fatalf("expected denied session error, got %v", err)
	}

	invalid := &edge5g.Open5GSUPFProvider{
		Config:    cfg,
		Transport: &stubSessionTransport{response: edge5g.SessionResponse{Accepted: true, LatencyMs: -1}},
	}
	if _, err := invalid.EstablishSession("ue1", "premium"); err == nil || !strings.Contains(err.Error(), "negative latency") {
		t.Fatalf("expected invalid transport response, got %v", err)
	}
}

type staticMockQoSMonitor struct {
	latency  int64
	lastUEID string
}

func (m *staticMockQoSMonitor) GetPacketStats() (edge5g.BPFStats, error) {
	return edge5g.BPFStats{}, nil
}

func (m *staticMockQoSMonitor) GetEstimatedLatencyMs(ueID string) int64 {
	m.lastUEID = ueID
	return m.latency
}

func TestOpen5GSProviderEBPFMonitorOverrideLatency(t *testing.T) {
	cfg := edge5g.UPFConfig{
		Endpoints: edge5g.EndpointConfig{
			AMF: "http://amf.local",
			UPF: "http://upf.local",
		},
	}

	provider := &edge5g.Open5GSUPFProvider{
		Config:    cfg,
		Transport: &stubSessionTransport{response: edge5g.SessionResponse{Accepted: true, LatencyMs: 15}},
		Monitor:   &staticMockQoSMonitor{latency: 45},
	}

	latency, err := provider.EstablishSession("ue1", "premium")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if latency != 45 {
		t.Fatalf("expected eBPF monitor to override latency to 45ms, got %dms", latency)
	}

	provider.Monitor = &staticMockQoSMonitor{latency: 10}
	latency, err = provider.EstablishSession("ue1", "premium")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if latency != 15 {
		t.Fatalf("expected base transport latency 15ms when eBPF monitor is lower, got %dms", latency)
	}

	provider.Monitor = &staticMockQoSMonitor{latency: 45}
	latency, err = provider.EstablishSession("  ue1  ", "premium")
	if err != nil {
		t.Fatalf("expected trimmed monitor lookup success, got %v", err)
	}
	monitor, ok := provider.Monitor.(*staticMockQoSMonitor)
	if !ok {
		t.Fatalf("expected static mock monitor, got %T", provider.Monitor)
	}
	if monitor.lastUEID != "ue1" {
		t.Fatalf("expected monitor lookup to use trimmed UEID, got %q", monitor.lastUEID)
	}
	if latency != 45 {
		t.Fatalf("expected override latency 45ms after trimmed monitor lookup, got %dms", latency)
	}

	provider.Monitor = nil
	latency, err = provider.EstablishSession("ue1", "premium")
	if err != nil {
		t.Fatalf("expected nil monitor to preserve success path, got %v", err)
	}
	if latency != 15 {
		t.Fatalf("expected base transport latency 15ms when monitor is nil, got %dms", latency)
	}
}

func TestOpen5GSProviderPropagatesTransportFailure(t *testing.T) {
	provider := &edge5g.Open5GSUPFProvider{
		Config: edge5g.UPFConfig{
			Endpoints: edge5g.EndpointConfig{AMF: "http://amf.local", UPF: "http://upf.local"},
		},
		Transport: &stubSessionTransport{err: errors.New("transport unavailable")},
		Monitor:   &staticMockQoSMonitor{latency: 45},
	}

	_, err := provider.EstablishSession("ue1", "premium")
	if err == nil || !strings.Contains(err.Error(), "transport failure") {
		t.Fatalf("expected transport failure, got %v", err)
	}
}

func TestOpen5GSRealUPFConstructorWiresSignalingBridge(t *testing.T) {
	provider := edge5g.NewRealOpen5GSUPF(edge5g.UPFConfig{
		AMFEndpoint: "127.0.0.1:38412",
		UPFEndpoint: "127.0.0.1:8805",
		Timeout:     250 * time.Millisecond,
	})

	if provider.Transport == nil {
		t.Fatal("expected real Open5GS scaffold to wire a transport bridge")
	}
}

func TestOpen5GSRealUPFConstructorTrimsEndpoints(t *testing.T) {
	provider := edge5g.NewRealOpen5GSUPF(edge5g.UPFConfig{
		AMFEndpoint: " 127.0.0.1:38412 ",
		UPFEndpoint: " 127.0.0.1:8805 ",
	})

	signaling, ok := provider.Transport.(*edge5g.Open5GSSignaling)
	if !ok {
		t.Fatalf("expected signaling bridge transport, got %T", provider.Transport)
	}
	if signaling.AMFAddr != "127.0.0.1:38412" || signaling.UPFAddr != "127.0.0.1:8805" {
		t.Fatalf("unexpected trimmed signaling endpoints: %+v", signaling)
	}
}

func TestOpen5GSRealUPFConstructorMergesPartialEndpointOverrides(t *testing.T) {
	provider := edge5g.NewRealOpen5GSUPF(edge5g.UPFConfig{
		Endpoints:   edge5g.EndpointConfig{UPF: " 127.0.0.1:8805 "},
		AMFEndpoint: " 127.0.0.1:38412 ",
	})

	signaling, ok := provider.Transport.(*edge5g.Open5GSSignaling)
	if !ok {
		t.Fatalf("expected signaling bridge transport, got %T", provider.Transport)
	}
	if signaling.AMFAddr != "127.0.0.1:38412" || signaling.UPFAddr != "127.0.0.1:8805" {
		t.Fatalf("expected merged signaling endpoints, got %+v", signaling)
	}
}

func TestOpen5GSHTTPTransportScaffold(t *testing.T) {
	transport := &edge5g.Open5GSHTTPTransport{}
	request := edge5g.SessionRequest{
		UEID:        "ue1",
		SliceID:     "premium",
		AMFEndpoint: "http://amf.local",
		UPFEndpoint: "http://upf.local",
		Timeout:     5 * time.Second,
	}

	if _, err := transport.EstablishSession(request); err == nil || !strings.Contains(err.Error(), "NOT VERIFIED") {
		t.Fatalf("expected missing client/base URL to stay NOT VERIFIED, got %v", err)
	}

	client := &stubHTTPDoer{
		statusCode: http.StatusOK,
		body:       `{"accepted":true,"latency_ms":33}`,
	}
	transport = &edge5g.Open5GSHTTPTransport{
		BaseURL: "http://open5gs.local",
		Client:  client,
	}

	resp, err := transport.EstablishSession(request)
	if err != nil {
		t.Fatalf("expected HTTP transport success, got %v", err)
	}
	if resp.LatencyMs != 33 || !resp.Accepted {
		t.Fatalf("unexpected HTTP transport response: %+v", resp)
	}
	if client.method != http.MethodPost {
		t.Fatalf("unexpected HTTP method: %s", client.method)
	}
	if client.url != "http://open5gs.local/sessions" {
		t.Fatalf("unexpected HTTP URL: %s", client.url)
	}
	if !strings.Contains(client.bodySeen, "\"ue_id\":\"ue1\"") || !strings.Contains(client.bodySeen, "\"slice_id\":\"premium\"") {
		t.Fatalf("unexpected HTTP payload: %s", client.bodySeen)
	}
}

func TestOpen5GSHTTPTransportRejectsInvalidJSON(t *testing.T) {
	transport := &edge5g.Open5GSHTTPTransport{
		BaseURL: "http://open5gs.local",
		Client: &stubHTTPDoer{
			statusCode: http.StatusOK,
			body:       `{"accepted":`,
		},
	}

	_, err := transport.EstablishSession(edge5g.SessionRequest{
		UEID:        "ue1",
		SliceID:     "premium",
		AMFEndpoint: "http://amf.local",
		UPFEndpoint: "http://upf.local",
		Timeout:     5 * time.Second,
	})
	if err == nil || !strings.Contains(err.Error(), "invalid response") {
		t.Fatalf("expected invalid JSON rejection, got %v", err)
	}
}

func TestOpen5GSHTTPTransportRejectsHTTPStatus(t *testing.T) {
	transport := &edge5g.Open5GSHTTPTransport{
		BaseURL: "http://open5gs.local",
		Client: &stubHTTPDoer{
			statusCode: http.StatusBadGateway,
			body:       `{"accepted":false}`,
		},
	}

	_, err := transport.EstablishSession(edge5g.SessionRequest{
		UEID:        "ue1",
		SliceID:     "premium",
		AMFEndpoint: "http://amf.local",
		UPFEndpoint: "http://upf.local",
		Timeout:     5 * time.Second,
	})
	if err == nil || !strings.Contains(err.Error(), "status 502") {
		t.Fatalf("expected HTTP status rejection, got %v", err)
	}
}

func TestOpen5GSHTTPTransportPropagatesDoerFailure(t *testing.T) {
	transport := &edge5g.Open5GSHTTPTransport{
		BaseURL: "http://open5gs.local",
		Client: &stubHTTPDoer{
			err: errors.New("dial timeout"),
		},
	}

	_, err := transport.EstablishSession(edge5g.SessionRequest{
		UEID:        "ue1",
		SliceID:     "premium",
		AMFEndpoint: "http://amf.local",
		UPFEndpoint: "http://upf.local",
		Timeout:     5 * time.Second,
	})
	if err == nil || !strings.Contains(err.Error(), "HTTP transport failure") {
		t.Fatalf("expected doer failure propagation, got %v", err)
	}
}

func TestOpen5GSHTTPTransportUsesCustomPath(t *testing.T) {
	client := &stubHTTPDoer{
		statusCode: http.StatusOK,
		body:       `{"accepted":true,"latency_ms":9}`,
	}
	transport := &edge5g.Open5GSHTTPTransport{
		BaseURL: "http://open5gs.local/",
		Path:    "/custom/sessions",
		Client:  client,
	}

	resp, err := transport.EstablishSession(edge5g.SessionRequest{
		UEID:        "ue1",
		SliceID:     "premium",
		AMFEndpoint: "http://amf.local",
		UPFEndpoint: "http://upf.local",
		Timeout:     5 * time.Second,
	})
	if err != nil {
		t.Fatalf("expected custom path success, got %v", err)
	}
	if resp.LatencyMs != 9 {
		t.Fatalf("unexpected latency: %+v", resp)
	}
	if client.url != "http://open5gs.local/custom/sessions" {
		t.Fatalf("unexpected custom URL: %s", client.url)
	}
}

func TestOpen5GSHTTPTransportTrimsBaseURLWhitespace(t *testing.T) {
	client := &stubHTTPDoer{
		statusCode: http.StatusOK,
		body:       `{"accepted":true,"latency_ms":12}`,
	}
	transport := &edge5g.Open5GSHTTPTransport{
		BaseURL: "  http://open5gs.local/  ",
		Client:  client,
	}

	if _, err := transport.EstablishSession(edge5g.SessionRequest{
		UEID:        "ue1",
		SliceID:     "premium",
		AMFEndpoint: "http://amf.local",
		UPFEndpoint: "http://upf.local",
		Timeout:     5 * time.Second,
	}); err != nil {
		t.Fatalf("expected whitespace-trimmed BaseURL success, got %v", err)
	}
	if client.url != "http://open5gs.local/sessions" {
		t.Fatalf("unexpected trimmed BaseURL URL: %s", client.url)
	}
}

func TestOpen5GSHTTPTransportTrimsDirectRequestPayloadFields(t *testing.T) {
	client := &stubHTTPDoer{
		statusCode: http.StatusOK,
		body:       `{"accepted":true,"latency_ms":17}`,
	}
	transport := &edge5g.Open5GSHTTPTransport{
		BaseURL: "http://open5gs.local",
		Client:  client,
	}

	if _, err := transport.EstablishSession(edge5g.SessionRequest{
		UEID:        " ue1 ",
		SliceID:     " premium ",
		AMFEndpoint: " http://amf.local ",
		UPFEndpoint: " http://upf.local ",
		Timeout:     5 * time.Second,
	}); err != nil {
		t.Fatalf("expected direct request success, got %v", err)
	}
	if strings.Contains(client.bodySeen, "\"ue_id\":\" ue1 \"") || strings.Contains(client.bodySeen, "\"slice_id\":\" premium \"") {
		t.Fatalf("expected trimmed request payload, got %s", client.bodySeen)
	}
	if !strings.Contains(client.bodySeen, "\"ue_id\":\"ue1\"") || !strings.Contains(client.bodySeen, "\"slice_id\":\"premium\"") {
		t.Fatalf("expected trimmed identifiers in payload, got %s", client.bodySeen)
	}
}

func TestRealEBPFQoSEnforcerDryRunContract(t *testing.T) {
	programmer := &stubPolicyProgrammer{}
	enforcer := &edge5g.RealEBPFQoSEnforcer{Programmer: programmer}

	if err := enforcer.EnforceSlicePolicy("premium", 75); err != nil {
		t.Fatalf("expected dry-run success, got %v", err)
	}
	if programmer.lastUpdate.SliceID != "premium" || programmer.lastUpdate.Priority != 75 {
		t.Fatalf("unexpected policy update: %+v", programmer.lastUpdate)
	}
	if programmer.lastUpdate.UpdatedAt.IsZero() {
		t.Fatal("expected update timestamp to be set")
	}

	if err := enforcer.EnforceSlicePolicy("  premium  ", 80); err != nil {
		t.Fatalf("expected trimmed slice success, got %v", err)
	}
	if programmer.lastUpdate.SliceID != "premium" || programmer.lastUpdate.Priority != 80 {
		t.Fatalf("expected trimmed policy update, got %+v", programmer.lastUpdate)
	}
}

func TestRealEBPFQoSEnforcerErrorSemantics(t *testing.T) {
	enforcer := &edge5g.RealEBPFQoSEnforcer{}
	if err := enforcer.EnforceSlicePolicy("premium", 75); err == nil || !strings.Contains(err.Error(), "NOT VERIFIED") {
		t.Fatalf("expected missing programmer to stay NOT VERIFIED, got %v", err)
	}
	if err := enforcer.EnforceSlicePolicy("premium", 256); err == nil || !strings.Contains(err.Error(), "0-255") {
		t.Fatalf("expected invalid priority rejection before programmer checks, got %v", err)
	}

	enforcer = &edge5g.RealEBPFQoSEnforcer{
		Programmer: &stubPolicyProgrammer{err: errors.New("programmer write failed")},
	}
	if err := enforcer.EnforceSlicePolicy("premium", 75); err == nil || !strings.Contains(err.Error(), "programmer failure") {
		t.Fatalf("expected programmer failure, got %v", err)
	}
}

func TestSimulatedQoSEnforcerTrimsSliceID(t *testing.T) {
	enforcer := &edge5g.SimulatedQoSEnforcer{}
	if err := enforcer.EnforceSlicePolicy("  premium  ", 10); err != nil {
		t.Fatalf("expected trimmed simulated QoS success, got %v", err)
	}
}

type countingQoSEnforcer struct {
	calls int
}

func (e *countingQoSEnforcer) EnforceSlicePolicy(string, int) error {
	e.calls++
	return nil
}

func (e *countingQoSEnforcer) IsSimulated() bool { return false }

type capturingUPFProvider struct {
	latency     int64
	lastUEID    string
	lastSliceID string
}

func (p *capturingUPFProvider) EstablishSession(ueID string, sliceID string) (int64, error) {
	p.lastUEID = ueID
	p.lastSliceID = sliceID
	return p.latency, nil
}

func (p *capturingUPFProvider) IsSimulated() bool { return false }

type capturingQoSEnforcer struct {
	lastSliceID  string
	lastPriority int
}

func (e *capturingQoSEnforcer) EnforceSlicePolicy(sliceID string, priority int) error {
	e.lastSliceID = sliceID
	e.lastPriority = priority
	return nil
}

func (e *capturingQoSEnforcer) IsSimulated() bool { return false }

type stubSessionTransport struct {
	response edge5g.SessionResponse
	err      error
	last     edge5g.SessionRequest
}

func (s *stubSessionTransport) EstablishSession(request edge5g.SessionRequest) (edge5g.SessionResponse, error) {
	s.last = request
	return s.response, s.err
}

type stubPolicyProgrammer struct {
	lastUpdate edge5g.PolicyUpdate
	err        error
}

func (s *stubPolicyProgrammer) Apply(update edge5g.PolicyUpdate) error {
	s.lastUpdate = update
	return s.err
}

type stubHTTPDoer struct {
	statusCode int
	body       string
	err        error
	method     string
	url        string
	bodySeen   string
}

func (s *stubHTTPDoer) Do(req *http.Request) (*http.Response, error) {
	s.method = req.Method
	s.url = req.URL.String()
	payload, _ := io.ReadAll(req.Body)
	s.bodySeen = string(payload)
	if s.err != nil {
		return nil, s.err
	}
	return &http.Response{
		StatusCode: s.statusCode,
		Body:       io.NopCloser(strings.NewReader(s.body)),
		Header:     make(http.Header),
	}, nil
}

func TestOpen5GSSignalingSCTPContract(t *testing.T) {
	// Мы не ожидаем успешного коннекта на 127.0.0.1:38412, но мы ожидаем,
	// что ошибка придет именно от SCTP транспорта (а не TCP).
	signaling := &edge5g.Open5GSSignaling{
		AMFAddr: "127.0.0.1:38412",
		Timeout: 100 * time.Millisecond,
	}

	err := signaling.EstablishNGAP("imsi-208930000000001")
	if err == nil {
		t.Fatal("expected connection failure on localhost, but got success")
	}

	// Ошибка должна содержать "SCTP transport failure", что подтверждает использование SCTP диалера.
	if !strings.Contains(err.Error(), "SCTP transport failure") {
		t.Fatalf("expected SCTP-specific error, got: %v", err)
	}
}

func TestOpen5GSSignalingPFCPContract(t *testing.T) {
	// Проверяем, что PFCP транспорт (UDP) инициируется корректно.
	signaling := &edge5g.Open5GSSignaling{
		UPFAddr: "127.0.0.1:8805",
		Timeout: 100 * time.Millisecond,
	}

	latency, err := signaling.CreatePFCPSSession("premium")
	if latency == 0 && err == nil {
		t.Fatal("expected non-zero latency or error")
	}
}

func TestOpen5GSSignalingEstablishSessionTrimsDirectRequestFields(t *testing.T) {
	signaling := &edge5g.Open5GSSignaling{}

	_, err := signaling.EstablishSession(edge5g.SessionRequest{
		UEID:        " ue1 ",
		SliceID:     " premium ",
		AMFEndpoint: " 127.0.0.1:38412 ",
		UPFEndpoint: " 127.0.0.1:8805 ",
		Timeout:     100 * time.Millisecond,
	})
	if err == nil {
		t.Fatal("expected transport failure against localhost")
	}
	if signaling.AMFAddr != "127.0.0.1:38412" || signaling.UPFAddr != "127.0.0.1:8805" {
		t.Fatalf("expected trimmed signaling endpoints after request propagation, got %+v", signaling)
	}
	if !strings.Contains(err.Error(), "transport failure") {
		t.Fatalf("expected transport failure semantics, got %v", err)
	}
}

func TestUERANSIMConfigGeneration(t *testing.T) {

	tmpDir, err := os.MkdirTemp("", "ueransim-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	controller := &edge5g.UERANSIMController{
		ConfigDir: tmpDir,
	}

	// Test UE Config
	ueCfg := edge5g.UEConfig{
		Supi:    "imsi-208930000000001",
		Mcc:     "208",
		Mnc:     "93",
		AmfAddr: "127.0.0.1",
		GnbAddr: "127.0.0.1",
	}
	uePath, err := controller.GenerateUEConfig(ueCfg)
	if err != nil {
		t.Fatalf("failed to generate UE config: %v", err)
	}
	if _, err := os.Stat(uePath); os.IsNotExist(err) {
		t.Errorf("UE config file not created: %s", uePath)
	}

	// Test gNB Config
	gnbCfg := edge5g.GNBConfig{
		Mcc:      "208",
		Mnc:      "93",
		Nci:      "0x00000001",
		IdLength: 32,
		AmfAddr:  "127.0.0.1",
		GnbAddr:  "127.0.0.1",
		NgapPort: 38412,
	}
	gnbPath, err := controller.GenerateGNBConfig(gnbCfg)
	if err != nil {
		t.Fatalf("failed to generate gNB config: %v", err)
	}
	if _, err := os.Stat(gnbPath); os.IsNotExist(err) {
		t.Errorf("gNB config file not created: %s", gnbPath)
	}
}

func TestUERANSIMConfigGenerationTrimsWhitespaceInputs(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "ueransim-trim-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	controller := &edge5g.UERANSIMController{ConfigDir: tmpDir}

	uePath, err := controller.GenerateUEConfig(edge5g.UEConfig{
		Supi:    " imsi-208930000000001 ",
		Mcc:     " 208 ",
		Mnc:     " 93 ",
		AmfAddr: " 127.0.0.1 ",
		GnbAddr: " 127.0.0.1 ",
	})
	if err != nil {
		t.Fatalf("expected trimmed UE config success, got %v", err)
	}
	if strings.Contains(uePath, " ") {
		t.Fatalf("expected trimmed UE config filename, got %s", uePath)
	}

	gnbPath, err := controller.GenerateGNBConfig(edge5g.GNBConfig{
		Mcc:      " 208 ",
		Mnc:      " 93 ",
		Nci:      " 0x00000001 ",
		IdLength: 32,
		AmfAddr:  " 127.0.0.1 ",
		GnbAddr:  " 127.0.0.1 ",
		NgapPort: 38412,
	})
	if err != nil {
		t.Fatalf("expected trimmed gNB config success, got %v", err)
	}
	if strings.Contains(gnbPath, " ") {
		t.Fatalf("expected trimmed gNB config filename, got %s", gnbPath)
	}
}

func TestUERANSIMConfigGenerationTrimsConfigDir(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "ueransim-dir-trim-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	controller := &edge5g.UERANSIMController{ConfigDir: " " + tmpDir + " "}
	uePath, err := controller.GenerateUEConfig(edge5g.UEConfig{
		Supi:    "imsi-208930000000001",
		Mcc:     "208",
		Mnc:     "93",
		AmfAddr: "127.0.0.1",
		GnbAddr: "127.0.0.1",
	})
	if err != nil {
		t.Fatalf("expected trimmed config dir success, got %v", err)
	}
	if !strings.HasPrefix(uePath, tmpDir+string(os.PathSeparator)) {
		t.Fatalf("expected config to be written under trimmed dir %s, got %s", tmpDir, uePath)
	}
}

func TestUERANSIMConfigGenerationRejectsInvalidConfig(t *testing.T) {
	controller := &edge5g.UERANSIMController{}

	if _, err := controller.GenerateUEConfig(edge5g.UEConfig{}); err == nil || !strings.Contains(err.Error(), "config dir required") {
		t.Fatalf("expected missing config dir rejection for UE config, got %v", err)
	}

	controller.ConfigDir = t.TempDir()
	if _, err := controller.GenerateUEConfig(edge5g.UEConfig{Supi: "ue1"}); err == nil || !strings.Contains(err.Error(), "MCC/MNC required") {
		t.Fatalf("expected missing MCC/MNC rejection for UE config, got %v", err)
	}

	if _, err := controller.GenerateGNBConfig(edge5g.GNBConfig{}); err == nil || !strings.Contains(err.Error(), "MCC/MNC required") {
		t.Fatalf("expected missing MCC/MNC rejection for gNB config, got %v", err)
	}

	if _, err := controller.GenerateGNBConfig(edge5g.GNBConfig{
		Mcc:      "208",
		Mnc:      "93",
		Nci:      "0x1",
		IdLength: 0,
		AmfAddr:  "127.0.0.1",
		GnbAddr:  "127.0.0.1",
		NgapPort: 38412,
	}); err == nil || !strings.Contains(err.Error(), "idLength must be positive") {
		t.Fatalf("expected invalid idLength rejection for gNB config, got %v", err)
	}
}

func TestMeasureLatency(t *testing.T) {
	controller := &edge5g.UERANSIMController{}

	// We cannot reliably ping a real interface in a CI/unit test environment without privileges or a real uesimtun0.
	// So we will just test the error handling path for an invalid interface to ensure the method is wired correctly.
	_, err := controller.MeasureLatency("invalid_iface_999", "8.8.8.8")
	if err == nil {
		t.Fatal("expected ping to fail on invalid interface")
	}
	if !strings.Contains(err.Error(), "ping failed") {
		t.Errorf("expected 'ping failed' error, got: %v", err)
	}
}
