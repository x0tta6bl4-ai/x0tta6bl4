package edge5g_test

import (
	"errors"
	"io"
	"net/http"
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

func TestOpen5GSProviderPropagatesTransportFailure(t *testing.T) {
	provider := &edge5g.Open5GSUPFProvider{
		Config: edge5g.UPFConfig{
			Endpoints: edge5g.EndpointConfig{AMF: "http://amf.local", UPF: "http://upf.local"},
		},
		Transport: &stubSessionTransport{err: errors.New("transport unavailable")},
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
}

func TestRealEBPFQoSEnforcerErrorSemantics(t *testing.T) {
	enforcer := &edge5g.RealEBPFQoSEnforcer{}
	if err := enforcer.EnforceSlicePolicy("premium", 75); err == nil || !strings.Contains(err.Error(), "NOT VERIFIED") {
		t.Fatalf("expected missing programmer to stay NOT VERIFIED, got %v", err)
	}

	enforcer = &edge5g.RealEBPFQoSEnforcer{
		Programmer: &stubPolicyProgrammer{err: errors.New("programmer write failed")},
	}
	if err := enforcer.EnforceSlicePolicy("premium", 75); err == nil || !strings.Contains(err.Error(), "programmer failure") {
		t.Fatalf("expected programmer failure, got %v", err)
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
