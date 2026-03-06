package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"text/template"
	"time"
)

const (
	minKernelMajor = 6
	minKernelMinor = 1
)

type loaderConfig struct {
	iface            string
	objectFile       string
	bpffsDir         string
	ciliumPolicyFile string
	ciliumNamespace  string
	tenantLabel      string
	controlNamespace string
	liveAttach       bool
	dumpStatus       bool
	applyPolicy      bool
	dryRun           bool
}

func main() {
	cfg := loaderConfig{}
	flag.StringVar(&cfg.iface, "iface", "eth0", "network interface to attach the XDP program to")
	flag.StringVar(&cfg.objectFile, "object", defaultObjectFile(), "bpf2go-generated CO-RE object file")
	flag.StringVar(&cfg.bpffsDir, "bpffs-dir", "/sys/fs/bpf/x0tta6bl4-prod", "bpffs directory for pinned programs and maps")
	flag.StringVar(&cfg.ciliumPolicyFile, "cilium-policy", "./cilium-networkpolicy.yaml", "output path for rendered CiliumNetworkPolicy")
	flag.StringVar(&cfg.ciliumNamespace, "namespace", "x0tta6bl4-mesh", "namespace where the Cilium policy should be created")
	flag.StringVar(&cfg.tenantLabel, "tenant-label", "tenant", "tenant label key used for zero-lateral-movement isolation")
	flag.StringVar(&cfg.controlNamespace, "control-namespace", "x0tta6bl4-control", "namespace allowed to manage the dataplane")
	flag.BoolVar(&cfg.liveAttach, "live-attach", false, "load and attach the XDP program to the selected interface")
	flag.BoolVar(&cfg.dumpStatus, "dump-status", false, "dump current interface/XDP status after verification")
	flag.BoolVar(&cfg.applyPolicy, "apply-policy", false, "apply the rendered CiliumNetworkPolicy with kubectl")
	flag.BoolVar(&cfg.dryRun, "dry-run", false, "force non-mutating verification even if --live-attach is set")
	flag.Parse()

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	if err := run(ctx, cfg); err != nil {
		fmt.Fprintf(os.Stderr, "ebpf prod loader failed: %v\n", err)
		os.Exit(1)
	}
}

func run(ctx context.Context, cfg loaderConfig) error {
	if cfg.liveAttach && cfg.dryRun {
		return fmt.Errorf("--live-attach and --dry-run are mutually exclusive")
	}
	if err := validateKernel(); err != nil {
		return err
	}
	if err := ensureFile("/sys/kernel/btf/vmlinux"); err != nil {
		return fmt.Errorf("BTF unavailable for CO-RE: %w", err)
	}
	if err := ensureTool("bpftool"); err != nil {
		return err
	}
	if err := ensureTool("ip"); err != nil {
		return err
	}
	if cfg.applyPolicy {
		if err := ensureTool("kubectl"); err != nil {
			return err
		}
	}

	shouldMutate := cfg.liveAttach && !cfg.dryRun
	if !shouldMutate {
		fmt.Printf("verification-only mode: kernel/BTF/tools validated for %s; no XDP attach performed\n", cfg.iface)
	} else {
		if err := os.MkdirAll(cfg.bpffsDir, 0o755); err != nil {
			return fmt.Errorf("create bpffs dir: %w", err)
		}
		if err := ensureFile(cfg.objectFile); err != nil {
			return fmt.Errorf("missing generated CO-RE object %s: %w", cfg.objectFile, err)
		}

		loadArgs := []string{
			"prog", "loadall",
			cfg.objectFile,
			filepath.Join(cfg.bpffsDir, "meshcore"),
			"pinmaps", filepath.Join(cfg.bpffsDir, "maps"),
		}
		if err := runCommand(ctx, "bpftool", loadArgs...); err != nil {
			return fmt.Errorf("load CO-RE objects: %w", err)
		}

		attachArgs := []string{
			"link", "set", "dev", cfg.iface,
			"xdp", "pinned", filepath.Join(cfg.bpffsDir, "meshcore", "xdp_mesh_filter_prog"),
		}
		if err := runCommand(ctx, "ip", attachArgs...); err != nil {
			return fmt.Errorf("attach xdp program: %w", err)
		}
	}

	if err := renderCiliumPolicy(cfg); err != nil {
		return err
	}

	if cfg.applyPolicy && !cfg.dryRun {
		if err := runCommand(ctx, "kubectl", "apply", "-f", cfg.ciliumPolicyFile); err != nil {
			return fmt.Errorf("apply Cilium policy: %w", err)
		}
	}

	if cfg.dumpStatus {
		if err := dumpStatus(ctx, cfg.iface); err != nil {
			return err
		}
	}

	fmt.Printf(
		"production eBPF loader prepared for interface=%s kernel>=6.1 object=%s benchmark_target_pps=>5M_not_measured_here\n",
		cfg.iface,
		cfg.objectFile,
	)
	return nil
}

func validateKernel() error {
	data, err := os.ReadFile("/proc/sys/kernel/osrelease")
	if err != nil {
		return fmt.Errorf("read kernel release: %w", err)
	}
	release := strings.TrimSpace(string(data))
	parts := strings.SplitN(release, ".", 3)
	if len(parts) < 2 {
		return fmt.Errorf("unexpected kernel release format: %s", release)
	}

	major, err := strconv.Atoi(parts[0])
	if err != nil {
		return fmt.Errorf("parse kernel major: %w", err)
	}
	minorPart := parts[1]
	minorDigits := takeNumericPrefix(minorPart)
	if minorDigits == "" {
		return fmt.Errorf("parse kernel minor from %s", release)
	}
	minor, err := strconv.Atoi(minorDigits)
	if err != nil {
		return fmt.Errorf("parse kernel minor: %w", err)
	}

	if major < minKernelMajor || (major == minKernelMajor && minor < minKernelMinor) {
		return fmt.Errorf("kernel %s is unsupported; require %d.%d+", release, minKernelMajor, minKernelMinor)
	}
	return nil
}

func renderCiliumPolicy(cfg loaderConfig) error {
	const policy = `apiVersion: cilium.io/v2
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

	type ciliumTemplateData struct {
		Namespace        string
		TenantLabel      string
		ControlNamespace string
	}

	file, err := os.Create(cfg.ciliumPolicyFile)
	if err != nil {
		return fmt.Errorf("create Cilium policy file: %w", err)
	}
	defer file.Close()

	tpl, err := template.New("cilium").Parse(policy)
	if err != nil {
		return fmt.Errorf("parse Cilium template: %w", err)
	}
	if err := tpl.Execute(file, ciliumTemplateData{
		Namespace:        cfg.ciliumNamespace,
		TenantLabel:      cfg.tenantLabel,
		ControlNamespace: cfg.controlNamespace,
	}); err != nil {
		return fmt.Errorf("render Cilium policy: %w", err)
	}
	return nil
}

func ensureTool(name string) error {
	if _, err := exec.LookPath(name); err != nil {
		return fmt.Errorf("required tool %s is not available", name)
	}
	return nil
}

func ensureFile(path string) error {
	info, err := os.Stat(path)
	if err != nil {
		return err
	}
	if info.IsDir() {
		return errors.New("expected a file, got a directory")
	}
	return nil
}

func runCommand(ctx context.Context, name string, args ...string) error {
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func dumpStatus(ctx context.Context, iface string) error {
	fmt.Printf("status: interface=%s\n", iface)
	if err := runCommand(ctx, "ip", "-details", "link", "show", "dev", iface); err != nil {
		return fmt.Errorf("dump interface status: %w", err)
	}
	if err := runCommand(ctx, "bpftool", "prog", "show"); err != nil {
		return fmt.Errorf("dump bpftool program status: %w", err)
	}
	return nil
}

func defaultObjectFile() string {
	switch runtime.GOARCH {
	case "amd64":
		return "./meshcore_x86_bpfel.o"
	case "arm64":
		return "./meshcore_arm64_bpfel.o"
	default:
		return "./meshcore_x86_bpfel.o"
	}
}

func takeNumericPrefix(value string) string {
	var out strings.Builder
	for _, ch := range value {
		if ch < '0' || ch > '9' {
			break
		}
		out.WriteRune(ch)
	}
	return out.String()
}
