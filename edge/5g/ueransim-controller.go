package edge5g

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"text/template"
	"time"
)

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

// GenerateUEConfig writes a YAML configuration for nr-ue.
func (c *UERANSIMController) GenerateUEConfig(cfg UEConfig) (string, error) {
	tmpl, err := template.New("ue-config").Parse(ueTemplate)
	if err != nil {
		return "", err
	}

	fileName := fmt.Sprintf("ue-%s.yaml", cfg.Supi)
	fullPath := filepath.Join(c.ConfigDir, fileName)

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
	Mcc        string
	Mnc        string
	Nci        string
	IdLength   int
	Tac        string
	AmfAddr    string
	GnbAddr    string
	NgapPort   int
	GtpPort    int
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

// GenerateGNBConfig writes a YAML configuration for nr-gnb.
func (c *UERANSIMController) GenerateGNBConfig(cfg GNBConfig) (string, error) {
	tmpl, err := template.New("gnb-config").Parse(gnbTemplate)
	if err != nil {
		return "", err
	}

	fileName := fmt.Sprintf("gnb-%s.yaml", cfg.Nci)
	fullPath := filepath.Join(c.ConfigDir, fileName)

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
	cmd := exec.Command("ping", "-I", interfaceName, "-c", "1", "-W", "1", targetIP)
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
