package v1alpha1

import metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

type MeshClusterPhase string

const (
	MeshClusterPhasePending      MeshClusterPhase = "Pending"
	MeshClusterPhaseInitializing MeshClusterPhase = "Initializing"
	MeshClusterPhaseRunning      MeshClusterPhase = "Running"
	MeshClusterPhaseDegraded     MeshClusterPhase = "Degraded"
	MeshClusterPhaseHealing      MeshClusterPhase = "Healing"
	MeshClusterPhaseTerminating  MeshClusterPhase = "Terminating"
)

type ImageSpec struct {
	Repository string `json:"repository,omitempty"`
	Tag        string `json:"tag,omitempty"`
	PullPolicy string `json:"pullPolicy,omitempty"`
}

type PQCEBPFSpec struct {
	Enabled       bool   `json:"enabled,omitempty"`
	PacketCounter bool   `json:"packetCounter,omitempty"`
	AntiReplay    bool   `json:"antiReplay,omitempty"`
	WindowSize    int32  `json:"windowSize,omitempty"`
	XDPMode       string `json:"xdpMode,omitempty"`
}

type PQCSpec struct {
	Enabled             bool        `json:"enabled,omitempty"`
	KEMAlgorithm        string      `json:"kemAlgorithm,omitempty"`
	DSAAlgorithm        string      `json:"dsaAlgorithm,omitempty"`
	KeyRotationInterval int32       `json:"keyRotationInterval,omitempty"`
	HybridMode          bool        `json:"hybridMode,omitempty"`
	EBPF                PQCEBPFSpec `json:"ebpf,omitempty"`
}

type CircuitSpec struct {
	Enabled          bool  `json:"enabled,omitempty"`
	FailureThreshold int32 `json:"failureThreshold,omitempty"`
	ResetTimeout     int32 `json:"resetTimeout,omitempty"`
	HalfOpenMaxCalls int32 `json:"halfOpenMaxCalls,omitempty"`
	SuccessThreshold int32 `json:"successThreshold,omitempty"`
}

type CacheSpec struct {
	Enabled        bool   `json:"enabled,omitempty"`
	TTLSeconds     int32  `json:"ttlSeconds,omitempty"`
	MaxEntries     int32  `json:"maxEntries,omitempty"`
	EvictionPolicy string `json:"evictionPolicy,omitempty"`
}

type FallbackSpec struct {
	Enabled       bool        `json:"enabled,omitempty"`
	RetryAttempts int32       `json:"retryAttempts,omitempty"`
	RetryDelay    float64     `json:"retryDelay,omitempty"`
	Circuit       CircuitSpec `json:"circuit,omitempty"`
	Cache         CacheSpec   `json:"cache,omitempty"`
}

type SPIFFESpec struct {
	Enabled           bool   `json:"enabled,omitempty"`
	SocketPath        string `json:"socketPath,omitempty"`
	RenewBeforeExpiry int32  `json:"renewBeforeExpiry,omitempty"`
}

type DAOGovernanceOnChainEIP1559Spec struct {
	MaxPriorityFeeGwei float64 `json:"maxPriorityFeeGwei,omitempty"`
	MaxFeeGwei         float64 `json:"maxFeeGwei,omitempty"`
}

type DAOGovernanceOnChainAuditSpec struct {
	LedgerPath string `json:"ledgerPath,omitempty"`
}

type DAOGovernanceOnChainSpec struct {
	Enabled           bool                            `json:"enabled,omitempty"`
	ChainID           int64                           `json:"chainId,omitempty"`
	RPC               string                          `json:"rpc,omitempty"`
	GovernanceAddress string                          `json:"governanceAddress,omitempty"`
	TokenAddress      string                          `json:"tokenAddress,omitempty"`
	EIP1559           DAOGovernanceOnChainEIP1559Spec `json:"eip1559,omitempty"`
	Audit             DAOGovernanceOnChainAuditSpec   `json:"audit,omitempty"`
}

type DAOGovernanceSpec struct {
	VotingPeriod    int32                    `json:"votingPeriod,omitempty"`
	QuorumThreshold float64                  `json:"quorumThreshold,omitempty"`
	ProposalExpiry  int32                    `json:"proposalExpiry,omitempty"`
	OnChain         DAOGovernanceOnChainSpec `json:"onChain,omitempty"`
}

type DAOBridgeSpec struct {
	Enabled         bool    `json:"enabled,omitempty"`
	ChainID         int64   `json:"chainId,omitempty"`
	ContractAddress string  `json:"contractAddress,omitempty"`
	GasLimit        int64   `json:"gasLimit,omitempty"`
	MaxGasPriceGwei float64 `json:"maxGasPriceGwei,omitempty"`
	Confirmations   int32   `json:"confirmations,omitempty"`
}

type DAOSpec struct {
	Enabled    bool              `json:"enabled,omitempty"`
	Governance DAOGovernanceSpec `json:"governance,omitempty"`
	Bridge     DAOBridgeSpec     `json:"bridge,omitempty"`
}

type MeshNetworkingSpec struct {
	MaxNodes          int32 `json:"maxNodes,omitempty"`
	HeartbeatInterval int32 `json:"heartbeatInterval,omitempty"`
	RouteOptimization bool  `json:"routeOptimization,omitempty"`
	GossipFanout      int32 `json:"gossipFanout,omitempty"`
}

type MAPEKSpec struct {
	Enabled           bool  `json:"enabled,omitempty"`
	MonitorInterval   int32 `json:"monitorInterval,omitempty"`
	AnalysisWindow    int32 `json:"analysisWindow,omitempty"`
	AdaptationEnabled bool  `json:"adaptationEnabled,omitempty"`
}

type MeshClusterSpec struct {
	Replicas    int32              `json:"replicas,omitempty"`
	TrustDomain string             `json:"trustDomain,omitempty"`
	Image       ImageSpec          `json:"image,omitempty"`
	PQC         PQCSpec            `json:"pqc,omitempty"`
	Fallback    FallbackSpec       `json:"fallback,omitempty"`
	SPIFFE      SPIFFESpec         `json:"spiffe,omitempty"`
	DAO         DAOSpec            `json:"dao,omitempty"`
	Mesh        MeshNetworkingSpec `json:"mesh,omitempty"`
	MAPEK       MAPEKSpec          `json:"mapek,omitempty"`
}

type PQCStatus struct {
	RotationsCompleted   int32        `json:"rotationsCompleted,omitempty"`
	LastRotation         *metav1.Time `json:"lastRotation,omitempty"`
	ActiveSessionCount   int32        `json:"activeSessionCount,omitempty"`
	PacketCounterEnabled bool         `json:"packetCounterEnabled,omitempty"`
}

type BridgeStatus struct {
	Connected    bool   `json:"connected,omitempty"`
	ChainID      int64  `json:"chainId,omitempty"`
	LastMintTx   string `json:"lastMintTx,omitempty"`
	PendingMints int32  `json:"pendingMints,omitempty"`
}

type MeshClusterStatus struct {
	Phase              MeshClusterPhase   `json:"phase,omitempty"`
	ReadyReplicas      int32              `json:"readyReplicas,omitempty"`
	ObservedGeneration int64              `json:"observedGeneration,omitempty"`
	PQCStatus          PQCStatus          `json:"pqcStatus,omitempty"`
	BridgeStatus       BridgeStatus       `json:"bridgeStatus,omitempty"`
	Conditions         []metav1.Condition `json:"conditions,omitempty"`
}

type MeshCluster struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   MeshClusterSpec   `json:"spec,omitempty"`
	Status MeshClusterStatus `json:"status,omitempty"`
}

type MeshClusterList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []MeshCluster `json:"items"`
}
