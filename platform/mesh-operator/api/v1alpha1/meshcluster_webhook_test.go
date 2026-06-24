package v1alpha1

import "testing"

func TestMeshClusterDefault(t *testing.T) {
	mc := &MeshCluster{}

	applyMeshClusterDefaults(mc)

	if mc.Spec.Replicas != defaultReplicas {
		t.Fatalf("replicas = %d, want %d", mc.Spec.Replicas, defaultReplicas)
	}
	if mc.Spec.TrustDomain != defaultTrustDomain {
		t.Fatalf("trustDomain = %q, want %q", mc.Spec.TrustDomain, defaultTrustDomain)
	}
	if mc.Spec.Image.Repository != defaultMeshNodeRepository {
		t.Fatalf("image.repository = %q, want %q", mc.Spec.Image.Repository, defaultMeshNodeRepository)
	}
	if mc.Spec.Image.Tag != defaultMeshNodeTag {
		t.Fatalf("image.tag = %q, want %q", mc.Spec.Image.Tag, defaultMeshNodeTag)
	}
	if mc.Spec.Image.PullPolicy != defaultPullPolicy {
		t.Fatalf("image.pullPolicy = %q, want %q", mc.Spec.Image.PullPolicy, defaultPullPolicy)
	}
	if mc.Spec.DAO.Bridge.ChainID != defaultDAOBridgeChainID {
		t.Fatalf("dao.bridge.chainId = %d, want %d", mc.Spec.DAO.Bridge.ChainID, defaultDAOBridgeChainID)
	}
}

func TestMeshClusterValidateCreateValid(t *testing.T) {
	mc := &MeshCluster{
		Spec: MeshClusterSpec{
			Replicas:    3,
			TrustDomain: "x0tta6bl4.mesh",
			Image: ImageSpec{
				Repository: "x0tta6bl4/mesh-node",
				Tag:        "3.4.0",
				PullPolicy: "IfNotPresent",
			},
			PQC: PQCSpec{
				Enabled:      true,
				KEMAlgorithm: "ML-KEM-768",
				DSAAlgorithm: "ML-DSA-65",
			},
			DAO: DAOSpec{
				Governance: DAOGovernanceSpec{
					OnChain: DAOGovernanceOnChainSpec{
						Enabled: true,
						ChainID: 84532,
						RPC:     "https://sepolia.base.org",
					},
				},
				Bridge: DAOBridgeSpec{
					Enabled:         true,
					ChainID:         84532,
					ContractAddress: "0x1111111111111111111111111111111111111111",
				},
			},
			MAPEK: MAPEKSpec{
				Enabled:         true,
				MonitorInterval: 10,
				AnalysisWindow:  30,
			},
		},
	}

	if err := validateMeshCluster(mc); err != nil {
		t.Fatalf("validateMeshCluster() unexpected error: %v", err)
	}
}

func TestMeshClusterValidateCreateInvalid(t *testing.T) {
	mc := &MeshCluster{
		Spec: MeshClusterSpec{
			Replicas:    0,
			TrustDomain: "bad/domain",
			Image: ImageSpec{
				PullPolicy: "Sometimes",
			},
			PQC: PQCSpec{
				Enabled:      true,
				KEMAlgorithm: "NOPE",
				DSAAlgorithm: "NOPE",
			},
			DAO: DAOSpec{
				Governance: DAOGovernanceSpec{
					OnChain: DAOGovernanceOnChainSpec{
						Enabled: true,
						ChainID: 0,
						RPC:     "",
					},
				},
				Bridge: DAOBridgeSpec{
					Enabled:         true,
					ChainID:         0,
					ContractAddress: "",
				},
			},
			MAPEK: MAPEKSpec{
				Enabled:         true,
				MonitorInterval: 0,
				AnalysisWindow:  0,
			},
		},
	}

	if err := validateMeshCluster(mc); err == nil {
		t.Fatalf("validateMeshCluster() expected error, got nil")
	}
}
