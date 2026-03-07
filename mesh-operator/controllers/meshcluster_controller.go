package controllers

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/util/intstr"
	"k8s.io/client-go/tools/record"
	"k8s.io/client-go/util/retry"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"

	meshv1alpha1 "github.com/x0tta6bl4/mesh-operator/api/v1alpha1"
)

const (
	meshClusterFinalizer = "meshclusters.x0tta6bl4.io/finalizer"

	conditionReady       = "Ready"
	conditionProgressing = "Progressing"
	conditionDegraded    = "Degraded"

	defaultMeshNodeImage      = "x0tta6bl4/mesh-node:3.4.0"
	defaultMeshNodePullPolicy = corev1.PullIfNotPresent
)

type MeshClusterReconciler struct {
	client.Client
	Scheme   *runtime.Scheme
	Recorder record.EventRecorder
}

func (r *MeshClusterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	log := ctrl.LoggerFrom(ctx).WithValues("meshcluster", req.NamespacedName)

	var meshCluster meshv1alpha1.MeshCluster
	if err := r.Get(ctx, req.NamespacedName, &meshCluster); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	if meshCluster.DeletionTimestamp.IsZero() {
		if !controllerutil.ContainsFinalizer(&meshCluster, meshClusterFinalizer) {
			controllerutil.AddFinalizer(&meshCluster, meshClusterFinalizer)
			if err := r.Update(ctx, &meshCluster); err != nil {
				return ctrl.Result{}, err
			}
			return ctrl.Result{Requeue: true}, nil
		}
	} else {
		if controllerutil.ContainsFinalizer(&meshCluster, meshClusterFinalizer) {
			if err := r.cleanupExternalResources(ctx, &meshCluster); err != nil {
				return ctrl.Result{RequeueAfter: 10 * time.Second}, err
			}
			controllerutil.RemoveFinalizer(&meshCluster, meshClusterFinalizer)
			if err := r.Update(ctx, &meshCluster); err != nil {
				return ctrl.Result{}, err
			}
		}
		return ctrl.Result{}, nil
	}

	if err := r.reconcileConfigMap(ctx, &meshCluster); err != nil {
		return r.handleReconcileError(ctx, &meshCluster, err)
	}

	if err := r.reconcileService(ctx, &meshCluster); err != nil {
		return r.handleReconcileError(ctx, &meshCluster, err)
	}

	if err := r.reconcileDeployment(ctx, &meshCluster); err != nil {
		return r.handleReconcileError(ctx, &meshCluster, err)
	}

	if err := r.updateStatus(ctx, &meshCluster); err != nil {
		return ctrl.Result{RequeueAfter: 10 * time.Second}, err
	}

	requeueAfter := 15 * time.Second
	if meshCluster.Status.Phase == meshv1alpha1.MeshClusterPhaseRunning {
		requeueAfter = 2 * time.Minute
	}
	log.Info("reconciliation completed", "phase", meshCluster.Status.Phase, "readyReplicas", meshCluster.Status.ReadyReplicas)
	return ctrl.Result{RequeueAfter: requeueAfter}, nil
}

func (r *MeshClusterReconciler) handleReconcileError(ctx context.Context, meshCluster *meshv1alpha1.MeshCluster, reconcileErr error) (ctrl.Result, error) {
	if err := r.markDegraded(ctx, meshCluster, reconcileErr); err != nil {
		return ctrl.Result{}, fmt.Errorf("reconcile error: %v; status update error: %w", reconcileErr, err)
	}
	return ctrl.Result{}, reconcileErr
}

func (r *MeshClusterReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&meshv1alpha1.MeshCluster{}).
		Owns(&corev1.ConfigMap{}).
		Owns(&corev1.Service{}).
		Owns(&appsv1.Deployment{}).
		Complete(r)
}

func (r *MeshClusterReconciler) reconcileConfigMap(ctx context.Context, meshCluster *meshv1alpha1.MeshCluster) error {
	payload, err := json.MarshalIndent(meshCluster.Spec, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal meshcluster spec: %w", err)
	}

	cm := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      r.configMapName(meshCluster),
			Namespace: meshCluster.Namespace,
		},
	}

	err = r.createOrUpdateWithRetry(ctx, cm, func() error {
		cm.Labels = r.labelsFor(meshCluster)
		cm.Data = map[string]string{
			"meshcluster.json": string(payload),
		}
		return controllerutil.SetControllerReference(meshCluster, cm, r.Scheme)
	})
	if err != nil {
		return fmt.Errorf("reconcile configmap: %w", err)
	}
	return nil
}

func (r *MeshClusterReconciler) reconcileService(ctx context.Context, meshCluster *meshv1alpha1.MeshCluster) error {
	svc := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      r.serviceName(meshCluster),
			Namespace: meshCluster.Namespace,
		},
	}

	err := r.createOrUpdateWithRetry(ctx, svc, func() error {
		svc.Labels = r.labelsFor(meshCluster)
		svc.Spec.Selector = r.podLabelsFor(meshCluster)
		svc.Spec.Ports = []corev1.ServicePort{
			{
				Name:       "mesh",
				Port:       8080,
				TargetPort: intstr.FromInt(8080),
				Protocol:   corev1.ProtocolTCP,
			},
		}
		return controllerutil.SetControllerReference(meshCluster, svc, r.Scheme)
	})
	if err != nil {
		return fmt.Errorf("reconcile service: %w", err)
	}
	return nil
}

func (r *MeshClusterReconciler) reconcileDeployment(ctx context.Context, meshCluster *meshv1alpha1.MeshCluster) error {
	replicas := r.desiredReplicas(meshCluster)
	labels := r.podLabelsFor(meshCluster)

	dep := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      r.deploymentName(meshCluster),
			Namespace: meshCluster.Namespace,
		},
	}

	err := r.createOrUpdateWithRetry(ctx, dep, func() error {
		dep.Labels = r.labelsFor(meshCluster)
		dep.Spec.Selector = &metav1.LabelSelector{MatchLabels: labels}
		dep.Spec.Replicas = &replicas
		dep.Spec.Template.ObjectMeta.Labels = labels
		dep.Spec.Template.Spec.Containers = []corev1.Container{
			{
				Name:            "mesh-node",
				Image:           r.desiredMeshNodeImage(meshCluster),
				ImagePullPolicy: r.desiredMeshNodePullPolicy(meshCluster),
				Ports: []corev1.ContainerPort{
					{
						Name:          "mesh",
						ContainerPort: 8080,
						Protocol:      corev1.ProtocolTCP,
					},
				},
				Env: []corev1.EnvVar{
					{Name: "MESH_CLUSTER_NAME", Value: meshCluster.Name},
					{Name: "MESH_CLUSTER_NAMESPACE", Value: meshCluster.Namespace},
					{Name: "MESH_TRUST_DOMAIN", Value: r.desiredTrustDomain(meshCluster)},
					{Name: "MESH_REPLICAS_DESIRED", Value: strconv.Itoa(int(replicas))},
					{Name: "PQC_ENABLED", Value: strconv.FormatBool(meshCluster.Spec.PQC.Enabled)},
					{Name: "PQC_KEM_ALGORITHM", Value: meshCluster.Spec.PQC.KEMAlgorithm},
					{Name: "PQC_DSA_ALGORITHM", Value: meshCluster.Spec.PQC.DSAAlgorithm},
					{Name: "PQC_HYBRID_MODE", Value: strconv.FormatBool(meshCluster.Spec.PQC.HybridMode)},
					{Name: "PQC_EBPF_ENABLED", Value: strconv.FormatBool(meshCluster.Spec.PQC.EBPF.Enabled)},
					{Name: "MESH_CONFIG_PATH", Value: "/etc/x0tta/meshcluster/meshcluster.json"},
				},
				VolumeMounts: []corev1.VolumeMount{
					{
						Name:      "meshcluster-config",
						MountPath: "/etc/x0tta/meshcluster",
						ReadOnly:  true,
					},
				},
			},
		}
		dep.Spec.Template.Spec.Volumes = []corev1.Volume{
			{
				Name: "meshcluster-config",
				VolumeSource: corev1.VolumeSource{
					ConfigMap: &corev1.ConfigMapVolumeSource{
						LocalObjectReference: corev1.LocalObjectReference{Name: r.configMapName(meshCluster)},
					},
				},
			},
		}
		return controllerutil.SetControllerReference(meshCluster, dep, r.Scheme)
	})
	if err != nil {
		return fmt.Errorf("reconcile deployment: %w", err)
	}

	return nil
}

func (r *MeshClusterReconciler) updateStatus(ctx context.Context, meshCluster *meshv1alpha1.MeshCluster) error {
	statusBase := meshCluster.DeepCopy()

	deployment := &appsv1.Deployment{}
	if err := r.Get(ctx, client.ObjectKey{Namespace: meshCluster.Namespace, Name: r.deploymentName(meshCluster)}, deployment); err != nil {
		if apierrors.IsNotFound(err) {
			meshCluster.Status.Phase = meshv1alpha1.MeshClusterPhasePending
			meshCluster.Status.ReadyReplicas = 0
		} else {
			return err
		}
	} else {
		desired := r.desiredReplicas(meshCluster)
		ready := deployment.Status.ReadyReplicas
		meshCluster.Status.ReadyReplicas = ready
		meshCluster.Status.Phase = r.phaseFor(meshCluster, ready, desired)
		meshCluster.Status.PQCStatus.PacketCounterEnabled = meshCluster.Spec.PQC.EBPF.PacketCounter
		meshCluster.Status.BridgeStatus.ChainID = meshCluster.Spec.DAO.Bridge.ChainID
		meshCluster.Status.BridgeStatus.Connected = meshCluster.Spec.DAO.Bridge.Enabled && ready > 0
	}

	meshCluster.Status.ObservedGeneration = meshCluster.Generation
	r.applyPhaseConditions(meshCluster)

	if err := r.Status().Patch(ctx, meshCluster, client.MergeFrom(statusBase)); err != nil {
		return fmt.Errorf("patch status: %w", err)
	}

	return nil
}

func (r *MeshClusterReconciler) markDegraded(ctx context.Context, meshCluster *meshv1alpha1.MeshCluster, reconcileErr error) error {
	r.Recorder.Eventf(meshCluster, corev1.EventTypeWarning, "ReconcileFailed", "Reconcile failed: %v", reconcileErr)
	statusBase := meshCluster.DeepCopy()

	meshCluster.Status.Phase = meshv1alpha1.MeshClusterPhaseDegraded
	meshCluster.Status.ObservedGeneration = meshCluster.Generation
	r.setStatusCondition(meshCluster, conditionReady, metav1.ConditionFalse, "ReconcileError", reconcileErr.Error())
	r.setStatusCondition(meshCluster, conditionProgressing, metav1.ConditionFalse, "ReconcileError", "reconciliation failed")
	r.setStatusCondition(meshCluster, conditionDegraded, metav1.ConditionTrue, "ReconcileError", reconcileErr.Error())

	if err := r.Status().Patch(ctx, meshCluster, client.MergeFrom(statusBase)); err != nil {
		return err
	}

	return nil
}

func (r *MeshClusterReconciler) cleanupExternalResources(ctx context.Context, meshCluster *meshv1alpha1.MeshCluster) error {
	resources := []client.Object{
		&appsv1.Deployment{
			ObjectMeta: metav1.ObjectMeta{
				Name:      r.deploymentName(meshCluster),
				Namespace: meshCluster.Namespace,
			},
		},
		&corev1.Service{
			ObjectMeta: metav1.ObjectMeta{
				Name:      r.serviceName(meshCluster),
				Namespace: meshCluster.Namespace,
			},
		},
		&corev1.ConfigMap{
			ObjectMeta: metav1.ObjectMeta{
				Name:      r.configMapName(meshCluster),
				Namespace: meshCluster.Namespace,
			},
		},
	}

	for _, obj := range resources {
		if err := r.Delete(ctx, obj); err != nil && !apierrors.IsNotFound(err) {
			return fmt.Errorf("delete %T %s/%s: %w", obj, obj.GetNamespace(), obj.GetName(), err)
		}
	}

	return nil
}

func (r *MeshClusterReconciler) applyPhaseConditions(meshCluster *meshv1alpha1.MeshCluster) {
	ready := meshCluster.Status.ReadyReplicas
	desired := r.desiredReplicas(meshCluster)
	phase := meshCluster.Status.Phase

	readyStatus := metav1.ConditionFalse
	readyReason := "MeshNodesNotReady"
	readyMessage := fmt.Sprintf("mesh nodes ready: %d/%d", ready, desired)
	if phase == meshv1alpha1.MeshClusterPhaseRunning {
		readyStatus = metav1.ConditionTrue
		readyReason = "MeshNodesReady"
		readyMessage = fmt.Sprintf("all mesh nodes ready: %d/%d", ready, desired)
	}
	r.setStatusCondition(meshCluster, conditionReady, readyStatus, readyReason, readyMessage)

	progressingStatus := metav1.ConditionFalse
	progressingReason := "Reconciled"
	progressingMessage := "mesh cluster resources are reconciled"
	if phase == meshv1alpha1.MeshClusterPhasePending || phase == meshv1alpha1.MeshClusterPhaseInitializing {
		progressingStatus = metav1.ConditionTrue
		progressingReason = "Reconciling"
		progressingMessage = fmt.Sprintf("mesh nodes progressing: %d/%d", ready, desired)
	}
	r.setStatusCondition(meshCluster, conditionProgressing, progressingStatus, progressingReason, progressingMessage)

	degradedStatus := metav1.ConditionFalse
	degradedReason := "Healthy"
	degradedMessage := "mesh cluster is healthy"
	if phase == meshv1alpha1.MeshClusterPhaseDegraded || phase == meshv1alpha1.MeshClusterPhaseHealing {
		degradedStatus = metav1.ConditionTrue
		degradedReason = "NotEnoughReadyReplicas"
		degradedMessage = fmt.Sprintf("mesh nodes ready: %d/%d", ready, desired)
	}
	r.setStatusCondition(meshCluster, conditionDegraded, degradedStatus, degradedReason, degradedMessage)
}

func (r *MeshClusterReconciler) setStatusCondition(
	meshCluster *meshv1alpha1.MeshCluster,
	conditionType string,
	status metav1.ConditionStatus,
	reason string,
	message string,
) {
	meta.SetStatusCondition(&meshCluster.Status.Conditions, metav1.Condition{
		Type:               conditionType,
		Status:             status,
		Reason:             reason,
		Message:            message,
		ObservedGeneration: meshCluster.Generation,
	})
}

func (r *MeshClusterReconciler) desiredReplicas(meshCluster *meshv1alpha1.MeshCluster) int32 {
	if meshCluster.Spec.Replicas < 1 {
		return 1
	}
	return meshCluster.Spec.Replicas
}

func (r *MeshClusterReconciler) desiredTrustDomain(meshCluster *meshv1alpha1.MeshCluster) string {
	if strings.TrimSpace(meshCluster.Spec.TrustDomain) == "" {
		return "x0tta6bl4.mesh"
	}
	return meshCluster.Spec.TrustDomain
}

func (r *MeshClusterReconciler) desiredMeshNodeImage(meshCluster *meshv1alpha1.MeshCluster) string {
	repository := strings.TrimSpace(meshCluster.Spec.Image.Repository)
	tag := strings.TrimSpace(meshCluster.Spec.Image.Tag)

	if repository == "" {
		if strings.TrimSpace(tag) == "" {
			return defaultMeshNodeImage
		}
		return "x0tta6bl4/mesh-node:" + tag
	}

	if tag == "" {
		return repository
	}
	return repository + ":" + tag
}

func (r *MeshClusterReconciler) desiredMeshNodePullPolicy(meshCluster *meshv1alpha1.MeshCluster) corev1.PullPolicy {
	policy := strings.TrimSpace(meshCluster.Spec.Image.PullPolicy)
	if policy == "" {
		return defaultMeshNodePullPolicy
	}
	pullPolicy := corev1.PullPolicy(policy)
	switch pullPolicy {
	case corev1.PullAlways, corev1.PullIfNotPresent, corev1.PullNever:
		return pullPolicy
	default:
		return defaultMeshNodePullPolicy
	}
}

func (r *MeshClusterReconciler) phaseFor(meshCluster *meshv1alpha1.MeshCluster, ready int32, desired int32) meshv1alpha1.MeshClusterPhase {
	if !meshCluster.DeletionTimestamp.IsZero() {
		return meshv1alpha1.MeshClusterPhaseTerminating
	}
	if ready == 0 {
		return meshv1alpha1.MeshClusterPhaseInitializing
	}
	if ready >= desired {
		return meshv1alpha1.MeshClusterPhaseRunning
	}
	if ready < desired {
		return meshv1alpha1.MeshClusterPhaseDegraded
	}
	return meshv1alpha1.MeshClusterPhasePending
}

func (r *MeshClusterReconciler) labelsFor(meshCluster *meshv1alpha1.MeshCluster) map[string]string {
	return map[string]string{
		"app.kubernetes.io/name":       "mesh-node",
		"app.kubernetes.io/instance":   meshCluster.Name,
		"app.kubernetes.io/managed-by": "x0tta-mesh-operator",
		"x0tta6bl4.io/meshcluster":     meshCluster.Name,
	}
}

func (r *MeshClusterReconciler) podLabelsFor(meshCluster *meshv1alpha1.MeshCluster) map[string]string {
	labels := r.labelsFor(meshCluster)
	labels["app.kubernetes.io/component"] = "mesh-node"
	return labels
}

func (r *MeshClusterReconciler) deploymentName(meshCluster *meshv1alpha1.MeshCluster) string {
	return meshCluster.Name + "-mesh"
}

func (r *MeshClusterReconciler) serviceName(meshCluster *meshv1alpha1.MeshCluster) string {
	return meshCluster.Name + "-mesh"
}

func (r *MeshClusterReconciler) configMapName(meshCluster *meshv1alpha1.MeshCluster) string {
	return meshCluster.Name + "-mesh-config"
}

func (r *MeshClusterReconciler) createOrUpdateWithRetry(
	ctx context.Context,
	obj client.Object,
	mutateFn controllerutil.MutateFn,
) error {
	return retry.RetryOnConflict(retry.DefaultRetry, func() error {
		_, err := controllerutil.CreateOrUpdate(ctx, r.Client, obj, mutateFn)
		return err
	})
}
