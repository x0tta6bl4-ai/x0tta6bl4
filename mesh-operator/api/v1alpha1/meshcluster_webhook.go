package v1alpha1

import (
	"context"
	"fmt"
	"regexp"
	"strings"

	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/util/validation/field"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/webhook/admission"
)

const (
	defaultMeshNodeRepository = "x0tta6bl4/mesh-node"
	defaultMeshNodeTag        = "3.4.0"
	defaultTrustDomain        = "x0tta6bl4.mesh"
	defaultPullPolicy         = "IfNotPresent"
	defaultReplicas           = int32(3)
	defaultDAOBridgeChainID   = int64(84532)
)

var (
	_ admission.CustomDefaulter = &meshClusterCustomDefaulter{}
	_ admission.CustomValidator = &meshClusterCustomValidator{}

	trustDomainRegex = regexp.MustCompile(`^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$`)
)

func (m *MeshCluster) SetupWebhookWithManager(mgr ctrl.Manager) error {
	return ctrl.NewWebhookManagedBy(mgr).
		For(m).
		WithDefaulter(&meshClusterCustomDefaulter{}).
		WithValidator(&meshClusterCustomValidator{}).
		Complete()
}

type meshClusterCustomDefaulter struct{}

func (d *meshClusterCustomDefaulter) Default(_ context.Context, obj runtime.Object) error {
	meshCluster, ok := obj.(*MeshCluster)
	if !ok {
		return fmt.Errorf("expected MeshCluster object, got %T", obj)
	}
	applyMeshClusterDefaults(meshCluster)
	return nil
}

type meshClusterCustomValidator struct{}

func (v *meshClusterCustomValidator) ValidateCreate(_ context.Context, obj runtime.Object) (admission.Warnings, error) {
	meshCluster, ok := obj.(*MeshCluster)
	if !ok {
		return nil, fmt.Errorf("expected MeshCluster object, got %T", obj)
	}
	return nil, validateMeshCluster(meshCluster)
}

func (v *meshClusterCustomValidator) ValidateUpdate(_ context.Context, _, newObj runtime.Object) (admission.Warnings, error) {
	meshCluster, ok := newObj.(*MeshCluster)
	if !ok {
		return nil, fmt.Errorf("expected MeshCluster object, got %T", newObj)
	}
	return nil, validateMeshCluster(meshCluster)
}

func (v *meshClusterCustomValidator) ValidateDelete(_ context.Context, _ runtime.Object) (admission.Warnings, error) {
	return nil, nil
}

func applyMeshClusterDefaults(meshCluster *MeshCluster) {
	if meshCluster.Spec.Replicas == 0 {
		meshCluster.Spec.Replicas = defaultReplicas
	}
	if strings.TrimSpace(meshCluster.Spec.TrustDomain) == "" {
		meshCluster.Spec.TrustDomain = defaultTrustDomain
	}
	if strings.TrimSpace(meshCluster.Spec.Image.Repository) == "" {
		meshCluster.Spec.Image.Repository = defaultMeshNodeRepository
	}
	if strings.TrimSpace(meshCluster.Spec.Image.Tag) == "" {
		meshCluster.Spec.Image.Tag = defaultMeshNodeTag
	}
	if strings.TrimSpace(meshCluster.Spec.Image.PullPolicy) == "" {
		meshCluster.Spec.Image.PullPolicy = defaultPullPolicy
	}
	if meshCluster.Spec.DAO.Bridge.ChainID == 0 {
		meshCluster.Spec.DAO.Bridge.ChainID = defaultDAOBridgeChainID
	}
}

func validateMeshCluster(meshCluster *MeshCluster) error {
	var allErrs field.ErrorList

	specPath := field.NewPath("spec")
	replicasPath := specPath.Child("replicas")
	trustDomainPath := specPath.Child("trustDomain")
	imagePath := specPath.Child("image")
	pqcPath := specPath.Child("pqc")
	daoPath := specPath.Child("dao")
	mapekPath := specPath.Child("mapek")

	if meshCluster.Spec.Replicas < 1 || meshCluster.Spec.Replicas > 1000 {
		allErrs = append(allErrs, field.Invalid(replicasPath, meshCluster.Spec.Replicas, "must be between 1 and 1000"))
	}

	trustDomain := strings.TrimSpace(meshCluster.Spec.TrustDomain)
	if trustDomain == "" {
		allErrs = append(allErrs, field.Required(trustDomainPath, "trustDomain is required"))
	} else if !trustDomainRegex.MatchString(trustDomain) {
		allErrs = append(allErrs, field.Invalid(trustDomainPath, meshCluster.Spec.TrustDomain, "must be a valid SPIFFE trust domain (dns-like, no scheme)"))
	}

	repository := strings.TrimSpace(meshCluster.Spec.Image.Repository)
	if repository == "" {
		allErrs = append(allErrs, field.Required(imagePath.Child("repository"), "image.repository is required"))
	}
	pullPolicy := strings.TrimSpace(meshCluster.Spec.Image.PullPolicy)
	if pullPolicy != "" {
		switch pullPolicy {
		case "Always", "IfNotPresent", "Never":
		default:
			allErrs = append(allErrs, field.NotSupported(
				imagePath.Child("pullPolicy"),
				pullPolicy,
				[]string{"Always", "IfNotPresent", "Never"},
			))
		}
	}

	if meshCluster.Spec.PQC.Enabled {
		switch meshCluster.Spec.PQC.KEMAlgorithm {
		case "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024":
		default:
			allErrs = append(allErrs, field.NotSupported(
				pqcPath.Child("kemAlgorithm"),
				meshCluster.Spec.PQC.KEMAlgorithm,
				[]string{"ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"},
			))
		}
		switch meshCluster.Spec.PQC.DSAAlgorithm {
		case "ML-DSA-44", "ML-DSA-65", "ML-DSA-87":
		default:
			allErrs = append(allErrs, field.NotSupported(
				pqcPath.Child("dsaAlgorithm"),
				meshCluster.Spec.PQC.DSAAlgorithm,
				[]string{"ML-DSA-44", "ML-DSA-65", "ML-DSA-87"},
			))
		}
	}

	if meshCluster.Spec.DAO.Governance.OnChain.Enabled {
		if meshCluster.Spec.DAO.Governance.OnChain.ChainID <= 0 {
			allErrs = append(allErrs, field.Invalid(
				daoPath.Child("governance", "onChain", "chainId"),
				meshCluster.Spec.DAO.Governance.OnChain.ChainID,
				"must be greater than 0 when onChain governance is enabled",
			))
		}
		if strings.TrimSpace(meshCluster.Spec.DAO.Governance.OnChain.RPC) == "" {
			allErrs = append(allErrs, field.Required(
				daoPath.Child("governance", "onChain", "rpc"),
				"rpc is required when onChain governance is enabled",
			))
		}
	}

	if meshCluster.Spec.DAO.Bridge.Enabled {
		if meshCluster.Spec.DAO.Bridge.ChainID <= 0 {
			allErrs = append(allErrs, field.Invalid(
				daoPath.Child("bridge", "chainId"),
				meshCluster.Spec.DAO.Bridge.ChainID,
				"must be greater than 0 when bridge is enabled",
			))
		}
		if strings.TrimSpace(meshCluster.Spec.DAO.Bridge.ContractAddress) == "" {
			allErrs = append(allErrs, field.Required(
				daoPath.Child("bridge", "contractAddress"),
				"contractAddress is required when bridge is enabled",
			))
		}
	}

	if meshCluster.Spec.MAPEK.Enabled {
		if meshCluster.Spec.MAPEK.MonitorInterval < 1 {
			allErrs = append(allErrs, field.Invalid(
				mapekPath.Child("monitorInterval"),
				meshCluster.Spec.MAPEK.MonitorInterval,
				"must be greater than 0 when MAPE-K is enabled",
			))
		}
		if meshCluster.Spec.MAPEK.AnalysisWindow < 1 {
			allErrs = append(allErrs, field.Invalid(
				mapekPath.Child("analysisWindow"),
				meshCluster.Spec.MAPEK.AnalysisWindow,
				"must be greater than 0 when MAPE-K is enabled",
			))
		}
	}

	if len(allErrs) == 0 {
		return nil
	}

	return apierrors.NewInvalid(
		schema.GroupKind{Group: GroupVersion.Group, Kind: "MeshCluster"},
		meshCluster.Name,
		allErrs,
	)
}
