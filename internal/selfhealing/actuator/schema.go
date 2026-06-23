package actuator

// ActionPlan represents the strict JSON structure we expect from the LLM.
type ActionPlan struct {
	Diagnosis string   `json:"diagnosis"`
	Actions   []Action `json:"actions"`
}

// Action represents a single remediation step.
type Action struct {
	// Command must be strictly from the whitelist, e.g., "restart_service", "patch_config", "flush_dns"
	Command string `json:"command"`
	// Target is the entity being acted upon, e.g., "v2ray.service" or "/usr/local/etc/xray/config.json"
	Target string `json:"target"`
	// Params holds dynamic parameters for the command, e.g., {"port": "10085"}
	Params map[string]string `json:"params,omitempty"`
}

// SystemDump represents the system state passed to the LLM for analysis.
type SystemDump struct {
	NodeID          string            `json:"node_id"`
	Timestamp       string            `json:"timestamp"`
	FailedComponent string            `json:"failed_component"`
	JournalLogs     []string          `json:"journal_logs"`
	DmesgLogs       []string          `json:"dmesg_logs"`
	Metrics         map[string]string `json:"metrics"`
}
