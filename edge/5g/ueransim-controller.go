package edge5g

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"text/template"
	"time"
)

var execCommand = exec.Command

// UEConfig defines parameters for a UERANSIM UE instance.
type UEConfig struct {
	Supi    string
	Mcc     string
	Mnc     string
	Key     string
	Op      string
	OpType  string
	AmfAddr string
	GnbAddr string
}

// UERANSIMController manages local 5G simulation lifecycle.
type UERANSIMController struct {
	BinaryPath string
	ConfigDir  string
}

const ueTemplate = `
supi: '{{.Supi}}'
mcc: '{{.Mcc}}'
mnc: '{{.Mnc}}'
key: '{{.Key}}'
op: '{{.Op}}'
opType: '{{.OpType}}'
amfAddrs: [ '{{.AmfAddr}}' ]
gnbSearchList: [ '{{.GnbAddr}}' ]
uacAic: {mps: false, mcs: false}
uacAcc: {normalClass: 0, class11: false, class12: false, class13: false, class14: false, class15: false}
sessions:
  - type: 'IPv4'
    apn: 'internet'
    slice: {sst: 1, sd: 0x010203}
configuredApnList: [ 'internet' ]
defaultPduSessionSnssai: {sst: 1, sd: 0x010203}
integrity: {IA1: true, IA2: true, IA3: true}
ciphering: {EA1: true, EA2: true, EA3: true}
`

func normalizeUEConfig(cfg UEConfig) UEConfig {
	cfg.Supi = strings.TrimSpace(cfg.Supi)
	cfg.Mcc = strings.TrimSpace(cfg.Mcc)
	cfg.Mnc = strings.TrimSpace(cfg.Mnc)
	cfg.Key = strings.TrimSpace(cfg.Key)
	cfg.Op = strings.TrimSpace(cfg.Op)
	cfg.OpType = strings.TrimSpace(cfg.OpType)
	cfg.AmfAddr = strings.TrimSpace(cfg.AmfAddr)
	cfg.GnbAddr = strings.TrimSpace(cfg.GnbAddr)
	return cfg
}

func validateUEConfig(cfg UEConfig, configDir string) error {
	if strings.TrimSpace(configDir) == "" {
		return fmt.Errorf("config dir required")
	}
	if cfg.Supi == "" {
		return fmt.Errorf("UE config SUPI required")
	}
	if cfg.Mcc == "" || cfg.Mnc == "" {
		return fmt.Errorf("UE config MCC/MNC required")
	}
	if cfg.AmfAddr == "" || cfg.GnbAddr == "" {
		return fmt.Errorf("UE config AMF/gNB addresses required")
	}
	return nil
}

// GenerateUEConfig writes a YAML configuration for nr-ue.
func (c *UERANSIMController) GenerateUEConfig(cfg UEConfig) (string, error) {
	cfg = normalizeUEConfig(cfg)
	configDir := strings.TrimSpace(c.ConfigDir)
	if err := validateUEConfig(cfg, configDir); err != nil {
		return "", err
	}

	tmpl, err := template.New("ue-config").Parse(ueTemplate)
	if err != nil {
		return "", err
	}

	if err := os.MkdirAll(configDir, 0o755); err != nil {
		return "", err
	}

	fileName := fmt.Sprintf("ue-%s.yaml", cfg.Supi)
	fullPath := filepath.Join(configDir, fileName)

	f, err := os.Create(fullPath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	if err := tmpl.Execute(f, cfg); err != nil {
		return "", err
	}

	return fullPath, nil
}

// GNBConfig defines parameters for a UERANSIM gNB instance.
type GNBConfig struct {
	Mcc      string
	Mnc      string
	Nci      string
	IdLength int
	Tac      string
	AmfAddr  string
	GnbAddr  string
	NgapPort int
	GtpPort  int
}

const gnbTemplate = `
mcc: '{{.Mcc}}'
mnc: '{{.Mnc}}'
nci: '{{.Nci}}'
idLength: {{.IdLength}}
tac: '{{.Tac}}'
linkIp: '{{.GnbAddr}}'
ngapIp: '{{.GnbAddr}}'
gtpIp: '{{.GnbAddr}}'
amfConfigs:
  - address: '{{.AmfAddr}}'
    port: {{.NgapPort}}
`

func normalizeGNBConfig(cfg GNBConfig) GNBConfig {
	cfg.Mcc = strings.TrimSpace(cfg.Mcc)
	cfg.Mnc = strings.TrimSpace(cfg.Mnc)
	cfg.Nci = strings.TrimSpace(cfg.Nci)
	cfg.Tac = strings.TrimSpace(cfg.Tac)
	cfg.AmfAddr = strings.TrimSpace(cfg.AmfAddr)
	cfg.GnbAddr = strings.TrimSpace(cfg.GnbAddr)
	return cfg
}

func validateGNBConfig(cfg GNBConfig, configDir string) error {
	if strings.TrimSpace(configDir) == "" {
		return fmt.Errorf("config dir required")
	}
	if cfg.Mcc == "" || cfg.Mnc == "" {
		return fmt.Errorf("gNB config MCC/MNC required")
	}
	if cfg.Nci == "" {
		return fmt.Errorf("gNB config NCI required")
	}
	if cfg.IdLength <= 0 {
		return fmt.Errorf("gNB config idLength must be positive")
	}
	if cfg.AmfAddr == "" || cfg.GnbAddr == "" {
		return fmt.Errorf("gNB config AMF/gNB addresses required")
	}
	if cfg.NgapPort <= 0 {
		return fmt.Errorf("gNB config NGAP port must be positive")
	}
	return nil
}

// GenerateGNBConfig writes a YAML configuration for nr-gnb.
func (c *UERANSIMController) GenerateGNBConfig(cfg GNBConfig) (string, error) {
	cfg = normalizeGNBConfig(cfg)
	configDir := strings.TrimSpace(c.ConfigDir)
	if err := validateGNBConfig(cfg, configDir); err != nil {
		return "", err
	}

	tmpl, err := template.New("gnb-config").Parse(gnbTemplate)
	if err != nil {
		return "", err
	}

	if err := os.MkdirAll(configDir, 0o755); err != nil {
		return "", err
	}

	fileName := fmt.Sprintf("gnb-%s.yaml", cfg.Nci)
	fullPath := filepath.Join(configDir, fileName)

	f, err := os.Create(fullPath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	if err := tmpl.Execute(f, cfg); err != nil {
		return "", err
	}

	return fullPath, nil
}

// MeasureLatency performs an ICMP ping over the specified interface (e.g., uesimtun0)
// and returns the round-trip latency. Useful for QoS monitoring.
func (c *UERANSIMController) MeasureLatency(interfaceName, targetIP string) (time.Duration, error) {
	interfaceName = strings.TrimSpace(interfaceName)
	targetIP = strings.TrimSpace(targetIP)
	if interfaceName == "" {
		return 0, fmt.Errorf("interface name required")
	}
	if targetIP == "" {
		return 0, fmt.Errorf("target IP required")
	}

	cmd := execCommand("ping", "-I", interfaceName, "-c", "1", "-W", "1", targetIP)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return 0, fmt.Errorf("ping failed: %v", err)
	}

	// Extract latency (time=X.XX ms)
	re := regexp.MustCompile(`time=([0-9.]+) ms`)
	matches := re.FindStringSubmatch(string(output))
	if len(matches) < 2 {
		return 0, fmt.Errorf("could not parse latency from ping output")
	}

	latencyMs, err := strconv.ParseFloat(matches[1], 64)
	if err != nil {
		return 0, fmt.Errorf("failed to parse latency float: %v", err)
	}

	return time.Duration(latencyMs * float64(time.Millisecond)), nil
}
