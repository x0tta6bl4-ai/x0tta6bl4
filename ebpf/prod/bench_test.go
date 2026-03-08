package main

// Dataplane benchmark suite — CI-safe (no root, no real NIC required).
//
// These benchmarks measure Go-level throughput of the components that sit in
// the critical path of the x0tta6bl4 production eBPF dataplane:
//
//   BenchmarkPolicyRender        — Cilium NetworkPolicy template rendering
//   BenchmarkPolicyRenderParallel— same, with GOMAXPROCS goroutines
//   BenchmarkKernelVersionParse  — kernel version string tokenisation
//   BenchmarkArchObjectFile      — architecture → BPF object resolution
//   BenchmarkXDPDecisionSimulator— synthetic allow/deny policy evaluator
//                                  (mirrors the XDP fast-path logic in Go)
//
// Road to 1 M PPS milestone
// --------------------------
//   The XDP attach + real pktgen path (ebpf/prod/benchmark-pps.sh) requires
//   root + hardware NIC and is tracked separately as a hardware gate.
//   These Go-level benchmarks give a repeatable, comparable CI signal that
//   tracks regressions in the Go control-plane, policy rendering and
//   decision-logic layers without hardware dependencies.
//
// Run locally:
//   go test -bench=. -benchmem -benchtime=5s ./ebpf/prod/
//
// Compare branches with benchstat:
//   go test -bench=. -count=8 ./ebpf/prod/ > old.txt
//   git checkout develop && go test -bench=. -count=8 ./ebpf/prod/ > new.txt
//   benchstat old.txt new.txt

import (
	"bytes"
	"os"
	"strings"
	"testing"
	"text/template"
)

// ---------------------------------------------------------------------------
// Helpers that replicate (but do not import from main) the template and
// the kernel-version tokeniser so tests never depend on unexported symbols.
// ---------------------------------------------------------------------------

const ciliumPolicyTemplate = `apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: x0tta6bl4-prod-ebpf
  namespace: {{ .Namespace }}
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: x0tta6bl4-agent
  ingress:
    - fromEndpoints:
        - matchLabels:
            {{ .TenantLabel }}: any
      toPorts:
        - ports:
            - port: "7000"
              protocol: TCP
            - port: "7443"
              protocol: TCP
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: {{ .ControlNamespace }}
  egress:
    - toEndpoints:
        - matchLabels:
            {{ .TenantLabel }}: any
      toPorts:
        - ports:
            - port: "7000"
              protocol: TCP
            - port: "7443"
              protocol: TCP
    - toEntities:
        - kube-apiserver
        - kube-dns
  enableDefaultDeny:
    ingress: true
    egress: true
`

type benchTemplateData struct {
	Namespace        string
	TenantLabel      string
	ControlNamespace string
}

var compiledPolicyTpl = func() *template.Template {
	tpl, err := template.New("cilium").Parse(ciliumPolicyTemplate)
	if err != nil {
		panic(err)
	}
	return tpl
}()

// renderPolicyTo renders the Cilium NetworkPolicy to the provided writer.
func renderPolicyTo(w *bytes.Buffer, ns, tenantLabel, controlNS string) error {
	w.Reset()
	return compiledPolicyTpl.Execute(w, benchTemplateData{
		Namespace:        ns,
		TenantLabel:      tenantLabel,
		ControlNamespace: controlNS,
	})
}

// takeNumericPrefixLocal is a copy of the unexported helper in loader.go.
func takeNumericPrefixLocal(value string) string {
	var out strings.Builder
	for _, ch := range value {
		if ch < '0' || ch > '9' {
			break
		}
		out.WriteRune(ch)
	}
	return out.String()
}

// ---------------------------------------------------------------------------
// XDP Decision Simulator
// ---------------------------------------------------------------------------
// Simulates the policy fast-path that the XDP program executes per-packet:
//   1. Tenant label lookup  (map access)
//   2. Port allow-list check (linear scan, mirrors BPF loop)
//   3. Action decision      (PASS / DROP)
//
// This is intentionally NOT the real XDP bytecode; it models the Go-side
// logic that mirrors the XDP behaviour for integration-level testing and
// gives a reproducible CI throughput number.

type xdpAction uint8

const (
	xdpPass xdpAction = iota
	xdpDrop
)

type xdpPacket struct {
	srcTenant string
	dstPort   uint16
	proto     string // "TCP" | "UDP"
}

type xdpPolicy struct {
	allowedPorts []uint16
	allowedProto string
}

func (p *xdpPolicy) decide(pkt xdpPacket) xdpAction {
	if pkt.proto != p.allowedProto {
		return xdpDrop
	}
	for _, port := range p.allowedPorts {
		if pkt.dstPort == port {
			return xdpPass
		}
	}
	return xdpDrop
}

// ---------------------------------------------------------------------------
// Benchmarks
// ---------------------------------------------------------------------------

// BenchmarkPolicyRender measures how fast the Cilium NetworkPolicy template
// can be rendered.  The template compile step is done once at package init;
// only the Execute step is measured.
func BenchmarkPolicyRender(b *testing.B) {
	var buf bytes.Buffer
	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		if err := renderPolicyTo(&buf, "x0tta6bl4-mesh", "tenant", "x0tta6bl4-control"); err != nil {
			b.Fatal(err)
		}
	}
	b.ReportMetric(float64(buf.Len()), "bytes/render")
}

// BenchmarkPolicyRenderParallel runs the render across all available CPUs.
func BenchmarkPolicyRenderParallel(b *testing.B) {
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		var buf bytes.Buffer
		for pb.Next() {
			if err := renderPolicyTo(&buf, "x0tta6bl4-mesh", "tenant", "x0tta6bl4-control"); err != nil {
				b.Fatal(err)
			}
		}
	})
}

// BenchmarkPolicyRenderToFile writes the rendered policy to a temp file,
// matching the actual production code path (os.Create + tpl.Execute).
func BenchmarkPolicyRenderToFile(b *testing.B) {
	f, err := os.CreateTemp(b.TempDir(), "cilium-policy-*.yaml")
	if err != nil {
		b.Fatal(err)
	}
	f.Close()
	path := f.Name()

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		cfg := loaderConfig{
			ciliumPolicyFile: path,
			ciliumNamespace:  "x0tta6bl4-mesh",
			tenantLabel:      "tenant",
			controlNamespace: "x0tta6bl4-control",
		}
		if err := renderCiliumPolicy(cfg); err != nil {
			b.Fatal(err)
		}
	}
}

// BenchmarkKernelVersionParse measures the throughput of the kernel version
// tokeniser used to validate the >=6.1 requirement.
func BenchmarkKernelVersionParse(b *testing.B) {
	inputs := []string{
		"6.1.0-37-generic",
		"6.14.0-37-generic",
		"5.15.0-89-generic",
		"6.8.0-49-azure",
	}
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		s := inputs[i%len(inputs)]
		parts := strings.SplitN(s, ".", 3)
		if len(parts) >= 2 {
			_ = takeNumericPrefixLocal(parts[1])
		}
	}
}

// BenchmarkArchObjectFile measures the architecture→object-file resolution.
func BenchmarkArchObjectFile(b *testing.B) {
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		_ = defaultObjectFile()
	}
}

// BenchmarkXDPDecisionSimulator measures synthetic per-packet policy
// evaluation throughput.  This models the hot-path logic without kernel
// interaction so it runs on any CI runner.
//
// Target: >= 5 M decisions/sec on a single core (matching the 5 M PPS
// hardware target as a Go-level lower bound; real XDP bytecode is faster).
func BenchmarkXDPDecisionSimulator(b *testing.B) {
	policy := &xdpPolicy{
		allowedPorts: []uint16{7000, 7443, 8080, 8443, 9090},
		allowedProto: "TCP",
	}

	packets := []xdpPacket{
		{srcTenant: "tenant-a", dstPort: 7000, proto: "TCP"},  // PASS
		{srcTenant: "tenant-b", dstPort: 7443, proto: "TCP"},  // PASS
		{srcTenant: "tenant-c", dstPort: 22, proto: "TCP"},    // DROP
		{srcTenant: "tenant-d", dstPort: 7000, proto: "UDP"},  // DROP (wrong proto)
		{srcTenant: "tenant-e", dstPort: 9090, proto: "TCP"},  // PASS
	}

	b.ReportAllocs()
	b.ResetTimer()
	var decisions uint64
	for i := 0; i < b.N; i++ {
		pkt := packets[i%len(packets)]
		_ = policy.decide(pkt)
		decisions++
	}
	b.ReportMetric(float64(b.N)/b.Elapsed().Seconds(), "decisions/sec")
}

// BenchmarkXDPDecisionSimulatorParallel is the parallel variant.
func BenchmarkXDPDecisionSimulatorParallel(b *testing.B) {
	policy := &xdpPolicy{
		allowedPorts: []uint16{7000, 7443, 8080, 8443, 9090},
		allowedProto: "TCP",
	}
	packets := []xdpPacket{
		{srcTenant: "tenant-a", dstPort: 7000, proto: "TCP"},
		{srcTenant: "tenant-b", dstPort: 22, proto: "TCP"},
		{srcTenant: "tenant-c", dstPort: 7443, proto: "TCP"},
	}

	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		i := 0
		for pb.Next() {
			_ = policy.decide(packets[i%len(packets)])
			i++
		}
	})
}
