package controllers

import (
	"context"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrlclient "sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"

	meshv1alpha1 "github.com/x0tta6bl4/mesh-operator/api/v1alpha1"
)

func TestDesiredMeshNodeImage(t *testing.T) {
	r := &MeshClusterReconciler{}

	tests := []struct {
		name string
		spec meshv1alpha1.ImageSpec
		want string
	}{
		{
			name: "defaults",
			spec: meshv1alpha1.ImageSpec{},
			want: defaultMeshNodeImage,
		},
		{
			name: "custom tag with default repository",
			spec: meshv1alpha1.ImageSpec{Tag: "3.4.1"},
			want: "x0tta6bl4/mesh-node:3.4.1",
		},
		{
			name: "repository only",
			spec: meshv1alpha1.ImageSpec{Repository: "ghcr.io/example/mesh-node"},
			want: "ghcr.io/example/mesh-node",
		},
		{
			name: "repository and tag",
			spec: meshv1alpha1.ImageSpec{
				Repository: "ghcr.io/example/mesh-node",
				Tag:        "stable",
			},
			want: "ghcr.io/example/mesh-node:stable",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			meshCluster := &meshv1alpha1.MeshCluster{
				Spec: meshv1alpha1.MeshClusterSpec{
					Image: tc.spec,
				},
			}
			got := r.desiredMeshNodeImage(meshCluster)
			if got != tc.want {
				t.Fatalf("desiredMeshNodeImage() = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestDesiredMeshNodePullPolicy(t *testing.T) {
	r := &MeshClusterReconciler{}

	tests := []struct {
		name string
		spec meshv1alpha1.ImageSpec
		want corev1.PullPolicy
	}{
		{
			name: "default",
			spec: meshv1alpha1.ImageSpec{},
			want: corev1.PullIfNotPresent,
		},
		{
			name: "always",
			spec: meshv1alpha1.ImageSpec{PullPolicy: string(corev1.PullAlways)},
			want: corev1.PullAlways,
		},
		{
			name: "never",
			spec: meshv1alpha1.ImageSpec{PullPolicy: string(corev1.PullNever)},
			want: corev1.PullNever,
		},
		{
			name: "invalid fallback",
			spec: meshv1alpha1.ImageSpec{PullPolicy: "InvalidPolicy"},
			want: corev1.PullIfNotPresent,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			meshCluster := &meshv1alpha1.MeshCluster{
				Spec: meshv1alpha1.MeshClusterSpec{
					Image: tc.spec,
				},
			}
			got := r.desiredMeshNodePullPolicy(meshCluster)
			if got != tc.want {
				t.Fatalf("desiredMeshNodePullPolicy() = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestApplyPhaseConditionsIsStableOnNoopUpdate(t *testing.T) {
	r := &MeshClusterReconciler{}
	meshCluster := &meshv1alpha1.MeshCluster{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "prod-mesh",
			Namespace:  "default",
			Generation: 3,
		},
		Spec: meshv1alpha1.MeshClusterSpec{
			Replicas: 2,
		},
		Status: meshv1alpha1.MeshClusterStatus{
			Phase:         meshv1alpha1.MeshClusterPhaseRunning,
			ReadyReplicas: 2,
		},
	}

	r.applyPhaseConditions(meshCluster)
	firstReady := meta.FindStatusCondition(meshCluster.Status.Conditions, conditionReady)
	if firstReady == nil {
		t.Fatalf("expected %s condition to be set", conditionReady)
	}
	firstTransition := firstReady.LastTransitionTime

	r.applyPhaseConditions(meshCluster)
	secondReady := meta.FindStatusCondition(meshCluster.Status.Conditions, conditionReady)
	if secondReady == nil {
		t.Fatalf("expected %s condition to be set after second pass", conditionReady)
	}

	if !firstTransition.Equal(&secondReady.LastTransitionTime) {
		t.Fatalf("LastTransitionTime changed on noop update: %v != %v", firstTransition, secondReady.LastTransitionTime)
	}
	if secondReady.Status != metav1.ConditionTrue {
		t.Fatalf("expected ready condition true, got %s", secondReady.Status)
	}
}

func TestCleanupExternalResources(t *testing.T) {
	scheme := testScheme()
	meshCluster := &meshv1alpha1.MeshCluster{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "prod-mesh",
			Namespace: "default",
		},
	}

	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "prod-mesh-mesh",
			Namespace: "default",
		},
	}
	service := &corev1.Service{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "prod-mesh-mesh",
			Namespace: "default",
		},
	}
	configMap := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "prod-mesh-mesh-config",
			Namespace: "default",
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithObjects(deployment, service, configMap).
		Build()

	r := &MeshClusterReconciler{
		Client: cl,
		Scheme: scheme,
	}

	if err := r.cleanupExternalResources(context.Background(), meshCluster); err != nil {
		t.Fatalf("cleanupExternalResources() error = %v", err)
	}

	for _, obj := range []ctrlclient.Object{
		&appsv1.Deployment{ObjectMeta: metav1.ObjectMeta{Name: deployment.Name, Namespace: deployment.Namespace}},
		&corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: service.Name, Namespace: service.Namespace}},
		&corev1.ConfigMap{ObjectMeta: metav1.ObjectMeta{Name: configMap.Name, Namespace: configMap.Namespace}},
	} {
		err := cl.Get(context.Background(), ctrlclient.ObjectKeyFromObject(obj), obj)
		if !apierrors.IsNotFound(err) {
			t.Fatalf("expected %T to be deleted, get err=%v", obj, err)
		}
	}
}

func TestUpdateStatusFromDeployment(t *testing.T) {
	scheme := testScheme()
	meshCluster := &meshv1alpha1.MeshCluster{
		ObjectMeta: metav1.ObjectMeta{
			Name:       "prod-mesh",
			Namespace:  "default",
			Generation: 7,
		},
		Spec: meshv1alpha1.MeshClusterSpec{
			Replicas: 2,
			PQC: meshv1alpha1.PQCSpec{
				EBPF: meshv1alpha1.PQCEBPFSpec{
					PacketCounter: true,
				},
			},
			DAO: meshv1alpha1.DAOSpec{
				Bridge: meshv1alpha1.DAOBridgeSpec{
					Enabled: true,
					ChainID: 84532,
				},
			},
		},
	}
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "prod-mesh-mesh",
			Namespace: "default",
		},
		Status: appsv1.DeploymentStatus{
			ReadyReplicas: 2,
		},
	}

	cl := fake.NewClientBuilder().
		WithScheme(scheme).
		WithStatusSubresource(&meshv1alpha1.MeshCluster{}).
		WithObjects(meshCluster, deployment).
		Build()

	r := &MeshClusterReconciler{
		Client: cl,
		Scheme: scheme,
	}

	var current meshv1alpha1.MeshCluster
	if err := cl.Get(context.Background(), ctrlclient.ObjectKeyFromObject(meshCluster), &current); err != nil {
		t.Fatalf("pre-get meshcluster: %v", err)
	}
	if err := r.updateStatus(context.Background(), &current); err != nil {
		t.Fatalf("updateStatus() error = %v", err)
	}

	var updated meshv1alpha1.MeshCluster
	if err := cl.Get(context.Background(), ctrlclient.ObjectKeyFromObject(meshCluster), &updated); err != nil {
		t.Fatalf("post-get meshcluster: %v", err)
	}

	if updated.Status.Phase != meshv1alpha1.MeshClusterPhaseRunning {
		t.Fatalf("phase = %s, want %s", updated.Status.Phase, meshv1alpha1.MeshClusterPhaseRunning)
	}
	if updated.Status.ReadyReplicas != 2 {
		t.Fatalf("readyReplicas = %d, want 2", updated.Status.ReadyReplicas)
	}
	if updated.Status.ObservedGeneration != 7 {
		t.Fatalf("observedGeneration = %d, want 7", updated.Status.ObservedGeneration)
	}
	if !updated.Status.PQCStatus.PacketCounterEnabled {
		t.Fatalf("packetCounterEnabled = false, want true")
	}
	if !updated.Status.BridgeStatus.Connected {
		t.Fatalf("bridge connected = false, want true")
	}
}

func testScheme() *runtime.Scheme {
	scheme := runtime.NewScheme()
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(meshv1alpha1.AddToScheme(scheme))
	return scheme
}
